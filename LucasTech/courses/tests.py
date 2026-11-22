"""Lantante Express : prix, affectation (ordre par distance, 10 s, verrou), portefeuille, annulation, API."""
import re
from datetime import datetime, timedelta, timezone as tz
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from Payments.solde import ajuster, portefeuille

from . import services as S
from .models import Annulation, Categorie, Course, OffreCourse, Parametres, Partenaire

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/courses/'
JOUR = datetime(2026, 11, 21, 10, 0, tzinfo=tz.utc)
NUIT = datetime(2026, 11, 21, 23, 30, tzinfo=tz.utc)
# Lomé : départ et arrivée à 0,03° de latitude (≈ 3,34 km à vol d'oiseau)
DEP = {'lat': 6.1300, 'lng': 1.2200, 'adresse': 'Départ'}
ARR = {'lat': 6.1600, 'lng': 1.2200, 'adresse': 'Arrivée'}

_n = 0


def compte(prenom='Ama'):
    global _n
    _n += 1
    return get_user_model().objects.create_user(email=f'{prenom.lower()}{_n}@example.com', password='x-Pass-12345',
                                                first_name=prenom, last_name='Test', is_verified=True)


def partenaire(cat, dist_km=1.0, quand=JOUR, note=5, **kw):
    """Partenaire validé, en ligne, à [dist_km] au sud du départ."""
    p = Partenaire.objects.create(user=compte('Kossi'), statut='valide', en_ligne=True, note=note,
                                  lat=DEP['lat'] - dist_km / 111.0, lng=DEP['lng'], position_le=quand, **kw)
    p.categories.add(cat)
    return p


@override_settings(STORAGES=STORAGES)
class PrixTests(TestCase):
    def setUp(self):
        self.moto = Categorie.objects.get(code='moto')
        self.clim = Categorie.objects.get(code='voiture-climatisee')

    def test_formule_et_arrondi(self):
        e = S.estimer(self.moto, DEP['lat'], DEP['lng'], ARR['lat'], ARR['lng'], quand=JOUR)
        km, mn = e['distance_km'], e['duree_min']
        self.assertAlmostEqual(km, 3.336 * 1.3, delta=0.02)          # haversine × 1,3
        self.assertEqual(mn, -(-km * 60 // 25))                         # 25 km/h, minute entamée
        brut = 150 + km * 100                                           # plus de prix à la minute
        self.assertEqual(e['prix'], 600)                                # 150 + 433,7 = 583,7 → 600
        self.assertEqual(e['prix'] % 50, 0)
        self.assertGreaterEqual(e['prix'], brut)
        self.assertEqual(e['prix_duree'], 0)
        self.assertEqual(e['total'], 600)

    def test_minimum(self):
        e = S.estimer(self.clim, DEP['lat'], DEP['lng'], DEP['lat'] + 0.001, DEP['lng'], quand=JOUR)
        self.assertEqual(e['prix'], 1000)
        self.assertTrue(e['minimum_applique'])

    def test_coefficient_de_nuit(self):
        jour = S.estimer(self.moto, DEP['lat'], DEP['lng'], ARR['lat'], ARR['lng'], quand=JOUR)['prix']
        nuit = S.estimer(self.moto, DEP['lat'], DEP['lng'], ARR['lat'], ARR['lng'], quand=NUIT)
        self.assertEqual(nuit['coefficient'], 1.25)
        self.assertEqual(nuit['prix'], S.arrondi_sup(563.7 * 1.25, 50))  # 705 → 750 (sans prix à la minute)
        self.assertGreater(nuit['prix'], jour)

    def test_reduction_fidelite(self):
        client = compte()
        for _ in range(10):
            Course.objects.create(client=client, categorie=self.moto, depart_lat=1, depart_lng=1, arrivee_lat=1,
                                  arrivee_lng=1, distance_km=1, duree_min=1, prix_estime=500, prix_final=500,
                                  statut='terminee', terminee_le=timezone.now())
        e = S.estimer(self.moto, DEP['lat'], DEP['lng'], ARR['lat'], ARR['lng'], client=client)
        self.assertGreater(e['reduction'], 0)
        self.assertLessEqual(e['reduction'], 1000)
        self.assertEqual(e['total'], e['prix'] - e['reduction'])


@override_settings(STORAGES=STORAGES)
class AffectationTests(TestCase):
    def setUp(self):
        self.moto = Categorie.objects.get(code='moto')
        self.client_user = compte()

    def _course(self, moyen='especes'):
        with mock.patch('django.utils.timezone.now', return_value=JOUR):
            return S.commander(self.client_user, self.moto, DEP, ARR, moyen=moyen)

    def test_ordre_par_distance(self):
        loin = partenaire(self.moto, 2.5)
        proche = partenaire(self.moto, 0.5)
        moyen = partenaire(self.moto, 1.5)
        c = self._course()
        o = c.offres.get()
        self.assertEqual(o.partenaire, proche)
        # pas de réponse en 10 s (après accusé de réception) → le suivant
        S.offre_en_cours(proche, JOUR + timedelta(seconds=1))
        S.avancer(c.pk, JOUR + timedelta(seconds=11))
        self.assertEqual(c.offres.order_by('id').last().partenaire, moyen)
        S.offre_en_cours(moyen, JOUR + timedelta(seconds=12))
        S.avancer(c.pk, JOUR + timedelta(seconds=22.5))
        self.assertEqual(c.offres.order_by('id').last().partenaire, loin)
        self.assertEqual(OffreCourse.objects.filter(course=c, reponse='ignoree').count(), 2)

    def test_attend_dix_secondes(self):
        p = partenaire(self.moto)
        c = self._course()
        S.offre_en_cours(p, JOUR + timedelta(seconds=1))  # accusé de réception
        S.avancer(c.pk, JOUR + timedelta(seconds=9))
        self.assertEqual(c.offres.get().reponse, 'en_attente')
        S.avancer(c.pk, JOUR + timedelta(seconds=11.5))
        self.assertEqual(c.offres.order_by('envoyee_le').first().reponse, 'ignoree')

    def test_sans_accuse_de_reception(self):
        a, b = partenaire(self.moto, 0.5), partenaire(self.moto, 1)
        c = self._course()
        S.avancer(c.pk, JOUR + timedelta(seconds=4))  # pas lu en 3 s
        self.assertEqual(c.offres.get(partenaire=a).reponse, 'expiree')
        self.assertEqual(c.offres.get(partenaire=b).reponse, 'en_attente')
        self.assertEqual(Partenaire.objects.get(pk=a.pk).offres_ignorees, 0)

    def test_verrou_acceptation_tardive(self):
        a, b = partenaire(self.moto, 0.5), partenaire(self.moto, 1)
        c = self._course()
        oa = S.offre_en_cours(a, JOUR + timedelta(seconds=1))
        with self.assertRaises(S.ErreurCourse) as e:
            S.accepter(a, oa.pk, JOUR + timedelta(seconds=12))  # trop tard
        self.assertEqual(e.exception.code, 'offre_expiree')
        S.avancer(c.pk, JOUR + timedelta(seconds=12))
        ob = S.offre_en_cours(b, JOUR + timedelta(seconds=13))
        S.accepter(b, ob.pk, JOUR + timedelta(seconds=14))
        c.refresh_from_db()
        self.assertEqual((c.statut, c.partenaire), ('acceptee', b))
        with self.assertRaises(S.ErreurCourse):
            S.accepter(a, oa.pk, JOUR + timedelta(seconds=15))
        with self.assertRaises(S.ErreurCourse):
            S.accepter(b, ob.pk, JOUR + timedelta(seconds=15))  # deux fois

    def test_hors_ligne_apres_trois_offres_ignorees(self):
        p = partenaire(self.moto)
        t = JOUR
        with mock.patch('django.utils.timezone.now', return_value=t):
            c = S.commander(compte(), self.moto, DEP, ARR)
        for i in range(3):  # seul coursier : la course lui est renvoyée, il la laisse passer 3 fois
            S.offre_en_cours(p, t + timedelta(seconds=1))
            Partenaire.objects.filter(pk=p.pk).update(position_le=t + timedelta(seconds=12))
            S.avancer(c.pk, t + timedelta(seconds=12))
            t += timedelta(seconds=12)
        p.refresh_from_db()
        self.assertFalse(p.en_ligne)

    def test_elargissement_puis_aucun_partenaire(self):
        p = partenaire(self.moto, 4)  # hors des 3 km, dans les 5 km
        c = self._course()
        c.refresh_from_db()
        self.assertEqual(float(c.rayon_km), 5.0)
        self.assertEqual(c.offres.get().partenaire, p)
        S.offre_en_cours(p, JOUR + timedelta(seconds=1))
        S.refuser(p, c.offres.get().pk, JOUR + timedelta(seconds=2))
        c.refresh_from_db()
        self.assertEqual(c.statut, 'recherche')  # personne d'autre, on réessaie jusqu'à 120 s
        S.avancer(c.pk, JOUR + timedelta(seconds=121))
        c.refresh_from_db()
        self.assertEqual(c.statut, 'aucun_partenaire')

    def test_dette_et_position_trop_ancienne(self):
        endette = partenaire(self.moto, 0.2)
        Partenaire.objects.filter(pk=endette.pk).update(solde=-10000)  # dette au plafond espèces
        vieux = partenaire(self.moto, 0.5, quand=JOUR - timedelta(seconds=60))
        ok = partenaire(self.moto, 1)
        c = self._course()
        self.assertEqual(c.offres.get().partenaire, ok)
        self.assertNotEqual(c.offres.get().partenaire, vieux)


@override_settings(STORAGES=STORAGES)
class PortefeuilleTests(TestCase):
    def setUp(self):
        self.moto = Categorie.objects.get(code='moto')
        self.client_user = compte()
        self.admin = compte('Admin')
        ajuster(self.client_user, 5000, "Test", self.admin)

    def _acceptee(self, moyen='portefeuille'):
        p = partenaire(self.moto)
        with mock.patch('django.utils.timezone.now', return_value=JOUR):
            c = S.commander(self.client_user, self.moto, DEP, ARR, moyen=moyen)
        o = S.offre_en_cours(p, JOUR + timedelta(seconds=1))
        S.accepter(p, o.pk, JOUR + timedelta(seconds=2))
        return Course.objects.get(pk=c.pk), p

    def _compteur(self, km, minutes):
        return S.prix_trajet(self.moto, km, minutes, 1, Parametres.get().arrondi)[0]

    def test_reservation_puis_debit_reel(self):
        """Le prix réservé n'est qu'une estimation : le client paie le prix du compteur (km et minutes réels)."""
        c, p = self._acceptee()
        self.assertEqual(portefeuille(self.client_user).solde, 5000 - 600)
        self.assertEqual(c.montant_reserve, 600)
        S.demarrer(p, c.pk, c.code_depart, JOUR + timedelta(minutes=5))
        Course.objects.filter(pk=c.pk).update(distance_reelle_km=3)
        c = S.terminer(p, c.pk, JOUR + timedelta(minutes=20))
        attendu = self._compteur(3, 15)
        self.assertEqual(c.prix_final, attendu)
        self.assertEqual(portefeuille(self.client_user).solde, 5000 - attendu)
        self.assertRegex(c.numero_recu, r'^LE-2026-\d{6}$')
        p.refresh_from_db()
        self.assertEqual(p.solde, attendu - int(attendu * 15 / 100))  # gain net (commission 15 %)

    def test_quelques_metres_tarif_de_base(self):
        """Quelques mètres seulement : le client paie le tarif de base (200 FCFA pour la moto)."""
        c, p = self._acceptee()
        S.demarrer(p, c.pk, c.code_depart, JOUR + timedelta(minutes=5))
        Course.objects.filter(pk=c.pk).update(distance_reelle_km=0.002)
        c = S.terminer(p, c.pk, JOUR + timedelta(minutes=5, seconds=30))
        self.assertEqual(self.moto.minimum, 200)
        self.assertEqual(c.prix_final, 200)
        self.assertEqual(portefeuille(self.client_user).solde, 4800)

    def test_attente_payante(self):
        c, p = self._acceptee()
        S.signaler_arrivee(p, c.pk, JOUR + timedelta(minutes=5), verifier_distance=False)
        S.demarrer(p, c.pk, c.code_depart, JOUR + timedelta(minutes=10))  # 5 min, dont 2 gratuites
        Course.objects.filter(pk=c.pk).update(distance_reelle_km=3)
        c = S.terminer(p, c.pk, JOUR + timedelta(minutes=25))
        attendu = self._compteur(3, 15) + 3 * 100  # compteur + 3 min d'attente payante × 100
        self.assertEqual(c.prix_final, attendu)
        self.assertEqual(portefeuille(self.client_user).solde, 5000 - attendu)

    def test_code_de_depart(self):
        Parametres.objects.filter(pk=1).update(code_depart_obligatoire=True)
        c, p = self._acceptee()
        with self.assertRaises(S.ErreurCourse):
            S.demarrer(p, c.pk, '99999')

    def test_sans_code_de_depart_par_defaut(self):
        c, p = self._acceptee()
        S.demarrer(p, c.pk, '')
        self.assertEqual(Course.objects.get(pk=c.pk).statut, 'en_cours')

    def test_code_exige_pour_une_categorie(self):
        Categorie.objects.filter(pk=self.moto.pk).update(code_depart_obligatoire=True)
        c, p = self._acceptee()
        with self.assertRaises(S.ErreurCourse):
            S.demarrer(p, c.pk, '')

    def test_annulation_en_recherche_libere_tout(self):
        with mock.patch('django.utils.timezone.now', return_value=JOUR):
            c = S.commander(self.client_user, self.moto, DEP, ARR, moyen='portefeuille')
        self.assertEqual(portefeuille(self.client_user).solde, 4400)
        S.annuler_par_client(c.pk, self.client_user, motif='Test', frais_acceptes=0, maintenant=JOUR + timedelta(seconds=5))
        self.assertEqual(portefeuille(self.client_user).solde, 5000)

    def test_annulation_apres_grace_avec_frais(self):
        c, p = self._acceptee()
        t = JOUR + timedelta(minutes=3)
        self.assertEqual(S.frais_annulation_client(c, t), (200, 'apres_grace'))
        with self.assertRaises(S.ErreurCourse):
            S.annuler_par_client(c.pk, self.client_user, motif='Test', frais_acceptes=0, maintenant=t)  # frais pas vus
        S.annuler_par_client(c.pk, self.client_user, motif='Test', frais_acceptes=200, maintenant=t)
        self.assertEqual(portefeuille(self.client_user).solde, 4800)
        p.refresh_from_db()
        self.assertEqual(p.solde, 200)

    def test_grace_et_retard_partenaire(self):
        c, p = self._acceptee()
        self.assertEqual(S.frais_annulation_client(c, JOUR + timedelta(minutes=1))[0], 0)
        tard = c.arrivee_prevue_le + timedelta(minutes=6)
        self.assertEqual(S.frais_annulation_client(c, tard), (0, 'partenaire_en_retard'))

    def test_especes_commission_en_dette_et_frais_reportes(self):
        c, p = self._acceptee(moyen='especes')
        t = JOUR + timedelta(minutes=3)
        S.annuler_par_client(c.pk, self.client_user, motif='Test', frais_acceptes=200, maintenant=t)
        self.assertEqual(Annulation.objects.get(course=c).frais_regles, False)
        self.assertEqual(S.frais_reportes(self.client_user), 200)
        # course suivante en espèces : frais ajoutés, commission en dette
        p2 = partenaire(self.moto, 0.3, quand=t)
        with mock.patch('django.utils.timezone.now', return_value=t):
            c2 = S.commander(self.client_user, self.moto, DEP, ARR)
        self.assertEqual(c2.total_client, 800)
        o = S.offre_en_cours(p2, t + timedelta(seconds=1))
        S.accepter(p2, o.pk, t + timedelta(seconds=2))
        S.demarrer(p2, c2.pk, Course.objects.get(pk=c2.pk).code_depart, t + timedelta(minutes=4))
        c2 = S.terminer(p2, c2.pk, t + timedelta(minutes=20))
        p2.refresh_from_db()
        # commission + frais encaissés pour Lantante
        self.assertEqual(p2.solde, -int(c2.prix_final * 15 / 100) - 200)
        self.assertEqual(S.frais_reportes(self.client_user), 0)

    def test_annulation_par_partenaire_relance(self):
        c, p = self._acceptee()
        autre = partenaire(self.moto, 2, quand=JOUR + timedelta(seconds=10))
        with mock.patch('django.utils.timezone.now', return_value=JOUR + timedelta(seconds=10)):
            S.annuler_par_partenaire(p, c.pk, 'Panne', maintenant=JOUR + timedelta(seconds=10))
        c.refresh_from_db()
        self.assertEqual(c.statut, 'recherche')
        self.assertEqual(c.offres.filter(reponse='en_attente').get().partenaire, autre)
        self.assertEqual(c.montant_reserve, 600)  # toujours réservé, même prix

    def test_remboursement_retenu_sur_partenaire(self):
        c, p = self._acceptee()
        S.demarrer(p, c.pk, c.code_depart, JOUR + timedelta(minutes=5))
        Course.objects.filter(pk=c.pk).update(distance_reelle_km=4)
        c = S.terminer(p, c.pk, JOUR + timedelta(minutes=20))
        apres = portefeuille(self.client_user).solde
        r = S.demander_remboursement(c, 300, 300, "Mauvais trajet", self.admin)
        self.assertEqual(r.statut, 'valide')
        self.assertEqual(portefeuille(self.client_user).solde, apres + 300)
        p.refresh_from_db()
        self.assertEqual(p.solde, c.prix_final - int(c.prix_final * 15 / 100) - 300)
        gros = S.demander_remboursement(c, 6000, 0, "Geste", self.admin)
        self.assertEqual(gros.statut, 'en_attente')  # au-delà de 5 000 : second admin
        with self.assertRaises(S.ErreurCourse):
            S.valider_remboursement(gros, self.admin)
        S.valider_remboursement(gros, compte('Second'))
        self.assertEqual(portefeuille(self.client_user).solde, apres + 300 + 6000)

    def test_solde_insuffisant(self):
        pauvre = compte()
        with self.assertRaises(S.ErreurCourse) as e:
            S.commander(pauvre, self.moto, DEP, ARR, moyen='portefeuille')
        self.assertEqual(e.exception.code, 'solde_insuffisant')
        self.assertFalse(Course.objects.filter(client=pauvre).exists())


@override_settings(STORAGES=STORAGES)
class ApiTests(APITestCase):
    def setUp(self):
        Parametres.objects.filter(pk=1).update(code_depart_obligatoire=True)
        self.moto = Categorie.objects.get(code='moto')
        self.user = compte()
        self.client.force_authenticate(self.user)

    def test_parcours_client(self):
        d = self.client.get(API + 'categories/').json()
        self.assertEqual([s['code'] for s in d['services']], ['moto', 'tricycle', 'voiture', 'cargo'])
        voiture = d['services'][2]['categories']
        self.assertEqual([c['active'] for c in voiture], [True, True, True])  # Prestige activé
        self.assertTrue(d['services'][1]['categories'][0]['active'])  # Tricycle activé
        self.assertEqual(d['services'][1]['categories'][0]['icone'], 'tricycle')
        pts = {'depart_lat': DEP['lat'], 'depart_lng': DEP['lng'], 'arrivee_lat': ARR['lat'], 'arrivee_lng': ARR['lng']}
        e = self.client.post(API + 'estimation/', pts, format='json').json()
        self.assertEqual(len(e['estimations']), 5)  # catégories actives seulement (Cargo : bientôt)
        r = self.client.post(API, {**pts, 'categorie': self.moto.pk, 'moyen_paiement': 'especes', 'repere': 'Pharmacie'},
                             format='json')
        self.assertEqual(r.status_code, 201, r.content)
        cid = r.json()['id']
        self.assertEqual(len(r.json()['code_depart']), 4)
        self.assertEqual(self.client.get(f'{API}{cid}/').json()['statut'], 'recherche')
        self.assertEqual(self.client.get(f'{API}{cid}/annuler/').json()['frais'], 0)
        r = self.client.post(API, {**pts, 'categorie': self.moto.pk}, format='json')
        self.assertEqual(r.json()['code'], 'course_en_cours')
        r = self.client.post(f'{API}{cid}/annuler/', {'frais': 0}, format='json')
        self.assertEqual(r.json()['code'], 'motif')
        r = self.client.post(f'{API}{cid}/annuler/', {'frais': 0, 'motif': 'Erreur de destination'}, format='json')
        self.assertEqual(r.json()['statut'], 'annulee')
        self.assertEqual(len(self.client.get(API).json()['resultats']), 1)

    def test_parcours_partenaire(self):
        coursier = compte('Kodjo')
        self.client.force_authenticate(coursier)
        self.assertEqual(self.client.get(API + 'partenaire/').status_code, 404)
        r = self.client.post(API + 'partenaire/', {'type': 'coursier', 'plaque': 'TG 1234 AB', 'vehicule': 'Haojue',
                                                   'type_vehicule': 'moto'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual({c['service'] for c in r.json()['categories']}, {'moto'})
        self.assertEqual(r.json()['statut'], 'a_completer')
        pos = {'en_ligne': True, 'lat': DEP['lat'] - 0.005, 'lng': DEP['lng']}
        self.assertEqual(self.client.post(API + 'partenaire/statut/', pos, format='json').json()['code'], 'non_valide')
        Partenaire.objects.filter(user=coursier).update(statut='valide')
        self.assertTrue(self.client.post(API + 'partenaire/statut/', pos, format='json').json()['en_ligne'])
        # le client commande
        self.client.force_authenticate(self.user)
        c = self.client.post(API, {'depart_lat': DEP['lat'], 'depart_lng': DEP['lng'], 'arrivee_lat': ARR['lat'],
                                   'arrivee_lng': ARR['lng'], 'categorie': self.moto.pk}, format='json').json()
        # le coursier interroge, accepte, démarre avec le code, termine
        self.client.force_authenticate(coursier)
        o = self.client.post(API + 'partenaire/offre/', {'lat': pos['lat'], 'lng': pos['lng']}, format='json').json()
        self.assertEqual(o['offre']['course']['id'], c['id'])
        self.assertNotIn('code_depart', o['offre']['course'])
        r = self.client.post(f"{API}partenaire/offres/{o['offre']['id']}/accepter/", format='json')
        self.assertEqual(r.json()['statut'], 'acceptee')
        base = f"{API}partenaire/courses/{c['id']}/"
        # trop loin : « Je suis arrivé » refusé ; au départ : arrivée automatique + message au client
        self.assertEqual(self.client.post(base + 'arrive/').json()['code'], 'trop_loin')
        o = self.client.post(API + 'partenaire/offre/', {'lat': DEP['lat'], 'lng': DEP['lng']}, format='json').json()
        self.assertEqual(o['course']['statut'], 'arrive')
        self.assertTrue(Course.objects.get(pk=c['id']).messages.filter(par='systeme').exists())
        self.assertEqual(self.client.post(base + 'demarrer/', {'code': '----'}, format='json').json()['code'], 'code')
        self.assertEqual(self.client.post(base + 'demarrer/', {'code': c['code_depart']}, format='json').status_code, 200)
        self.assertEqual(self.client.post(base + 'terminer/').json()['statut'], 'terminee')
        s = self.client.get(API + 'partenaire/solde/').json()
        fin = Course.objects.get(pk=c['id'])
        self.assertEqual(s['solde'], -int(fin.prix_final * 15 / 100))  # commission 15 % du prix au compteur
        # le client voit le reçu et note
        self.client.force_authenticate(self.user)
        rc = self.client.get(f"{API}{c['id']}/recu/").json()
        self.assertTrue(rc['numero'].startswith('LE-'))
        self.assertEqual(self.client.post(f"{API}{c['id']}/noter/", {'note': 5, 'motifs': ['Ponctualité']},
                                          format='json').json(), {'ok': True})
        self.assertEqual(self.client.post(f"{API}{c['id']}/noter/", {'note': 4}, format='json').json()['code'],
                         'deja_notee')

    def test_parametres_singleton(self):
        self.assertEqual(Parametres.get().pk, 1)
        self.assertEqual(Parametres.get().delai_reponse_s, 10)


@override_settings(STORAGES=STORAGES)
class DiscussionTests(APITestCase):
    def setUp(self):
        import tempfile
        from django.core.files.storage import FileSystemStorage
        from .models import MessageCourse
        champ = MessageCourse._meta.get_field('fichier')
        self._dossier = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        ancien, champ.storage = champ.storage, FileSystemStorage(location=self._dossier.name)
        self.addCleanup(setattr, champ, 'storage', ancien)
        self.addCleanup(self._dossier.cleanup)
        self.moto = Categorie.objects.get(code='moto')
        self.user = compte('Ama')
        self.p = partenaire(self.moto, 0.5, quand=timezone.now(), vehicule='Haojue rouge', plaque='TG 1234 AB')
        self.c = S.commander(self.user, self.moto, DEP, ARR)

    def _accepter(self):
        o = S.offre_en_cours(self.p)
        S.accepter(self.p, o.pk)

    def test_fermee_avant_acceptation(self):
        self.client.force_authenticate(self.user)
        r = self.client.post(f'{API}{self.c.pk}/messages/', {'texte': 'Allô'}, format='json')
        self.assertEqual(r.json()['code'], 'ferme')

    def test_message_automatique_et_echanges(self):
        self._accepter()
        self.client.force_authenticate(self.user)
        d = self.client.get(f'{API}{self.c.pk}/messages/').json()
        self.assertTrue(d['ouverte'])
        auto = d['messages'][0]
        self.assertEqual(auto['par'], 'systeme')
        self.assertIn('Bonjour Ama', auto['texte'])
        self.assertIn('Plaque : TG 1234 AB', auto['texte'])
        self.assertNotIn('{', auto['texte'])
        m = self.client.post(f'{API}{self.c.pk}/messages/', {'texte': "Où êtes-vous ?"}, format='json').json()
        self.client.post(f'{API}{self.c.pk}/messages/', {'type': 'position', 'lat': 6.13, 'lng': 1.22}, format='json')
        # le partenaire lit et répond ; accusé de lecture côté client
        self.client.force_authenticate(self.p.user)
        d = self.client.get(f'{API}{self.c.pk}/messages/').json()
        self.assertEqual((d['role'], d['non_lus']), ('partenaire', 3))
        self.client.post(f'{API}{self.c.pk}/messages/lus/', {}, format='json')
        self.client.post(f'{API}{self.c.pk}/messages/', {'texte': "J'arrive"}, format='json')
        self.client.force_authenticate(self.user)
        d = self.client.get(f'{API}{self.c.pk}/messages/', {'depuis': m['id']}).json()
        self.assertEqual([x['type'] for x in d['messages']], ['position', 'texte'])
        self.assertEqual(d['non_lus'], 1)
        self.assertGreaterEqual(d['lu_jusqua'], m['id'])
        self.assertEqual(self.client.get(f'{API}{self.c.pk}/').json()['discussion']['non_lus'], 1)

    def test_vocal_et_photo(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self._accepter()
        self.client.force_authenticate(self.user)
        v = SimpleUploadedFile('v.m4a', b'0' * 100, content_type='audio/mp4')
        r = self.client.post(f'{API}{self.c.pk}/messages/', {'type': 'audio', 'duree': 12, 'fichier': v})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.client.get(r.json()['fichier']).status_code, 200)
        long = SimpleUploadedFile('v.m4a', b'0' * 100, content_type='audio/mp4')
        r = self.client.post(f'{API}{self.c.pk}/messages/', {'type': 'audio', 'duree': 61, 'fichier': long})
        self.assertEqual(r.json()['code'], 'duree')
        exe = SimpleUploadedFile('x.exe', b'0', content_type='application/octet-stream')
        r = self.client.post(f'{API}{self.c.pk}/messages/', {'type': 'image', 'fichier': exe})
        self.assertEqual(r.json()['code'], 'fichier')

    def test_acces_reserve_et_lecture_seule(self):
        self._accepter()
        self.client.force_authenticate(compte('Intrus'))
        self.assertEqual(self.client.get(f'{API}{self.c.pk}/messages/').status_code, 404)
        S.demarrer(self.p, self.c.pk, Course.objects.get(pk=self.c.pk).code_depart)
        S.terminer(self.p, self.c.pk)
        Course.objects.filter(pk=self.c.pk).update(terminee_le=timezone.now() - timedelta(minutes=61))
        self.client.force_authenticate(self.user)
        d = self.client.get(f'{API}{self.c.pk}/messages/').json()
        self.assertFalse(d['ouverte'])
        self.assertTrue(d['messages'])
        r = self.client.post(f'{API}{self.c.pk}/messages/', {'texte': 'Merci'}, format='json')
        self.assertEqual(r.json()['code'], 'ferme')

    def test_message_a_l_arrivee(self):
        self._accepter()
        Partenaire.objects.filter(pk=self.p.pk).update(lat=DEP['lat'], lng=DEP['lng'])
        self.p.refresh_from_db()
        S.signaler_arrivee(self.p, self.c.pk)
        dernier = self.c.messages.last()
        self.assertEqual(dernier.par, 'systeme')
        self.assertIn('TG 1234 AB', dernier.texte)
        self.assertNotIn('{', dernier.texte)


@override_settings(STORAGES=STORAGES)
class VersementTests(APITestCase):
    def test_demande_et_paiement(self):
        moto = Categorie.objects.get(code='moto')
        p = partenaire(moto, mobile_money='+22890000009')
        S.mouvement_partenaire(p.pk, 3000, 'gain', motif='Test')
        self.client.force_authenticate(p.user)
        r = self.client.post(API + 'partenaire/versement/', {'montant': 1000}, format='json')
        self.assertEqual(r.json()['code'], 'montant')
        r = self.client.post(API + 'partenaire/versement/', {'montant': 2500}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        r = self.client.post(API + 'partenaire/versement/', {'montant': 2000}, format='json')
        self.assertEqual(r.json()['code'], 'solde')  # 2 500 déjà demandés sur 3 000
        from .models import DemandeVersement
        S.payer_versement(DemandeVersement.objects.get(), compte('Admin'))
        p.refresh_from_db()
        self.assertEqual(p.solde, 500)
        d = self.client.get(API + 'partenaire/solde/').json()
        self.assertEqual(d['versements'][0]['statut'], 'paye')
        self.assertEqual(d['versement_min'], 2000)

    def test_alerte_nouvelle_offre(self):
        from api_mobile.models import Notification
        moto = Categorie.objects.get(code='moto')
        p = partenaire(moto, quand=timezone.now())
        S.commander(compte(), moto, DEP, ARR)
        self.assertTrue(Notification.objects.filter(utilisateur=p.user, titre='Nouvelle course').exists())


@override_settings(STORAGES=STORAGES)
class PrixReelZonesTests(APITestCase):
    def setUp(self):
        self.moto = Categorie.objects.get(code='moto')
        self.user = compte()

    def _en_cours(self):
        p = partenaire(self.moto, 0.5, quand=timezone.now())
        c = S.commander(self.user, self.moto, DEP, ARR)
        o = S.offre_en_cours(p)
        S.accepter(p, o.pk)
        S.demarrer(p, c.pk, Course.objects.get(pk=c.pk).code_depart)
        return Course.objects.get(pk=c.pk), p

    def test_distance_reelle_plus_longue(self):
        c, p = self._en_cours()
        lat = DEP['lat']
        for _ in range(60):  # 60 pas de 0,002 degré (~220 m) : ~13 km parcourus pour 4,3 km prévus
            lat += 0.002
            S.suivre_position(p, lat, DEP['lng'])
        c = S.terminer(p, c.pk)
        self.assertGreater(c.prix_final, c.prix_estime)  # compteur : ~13 km au lieu de 4,3
        self.assertGreater(c.detail_prix['compteur_km'], 12)
        rc = self.client.force_authenticate(self.user) or self.client.get(f'{API}{c.pk}/recu/').json()
        self.assertEqual(rc['prix_annonce'], c.prix_estime)
        self.assertEqual(rc['prix'], c.prix_final)

    def test_petit_detour_sans_augmentation(self):
        c, p = self._en_cours()
        lat = DEP['lat']
        for _ in range(15):  # 15 × 220 m ≈ 3,3 km : sous la distance prévue + 15 %
            lat += 0.002
            S.suivre_position(p, lat, DEP['lng'])
        c = S.terminer(p, c.pk)
        self.assertLess(c.prix_final, c.prix_estime)  # trajet plus court que prévu : prix plus bas
        self.assertEqual(c.detail_prix['supplements'], [])

    def test_mention_dans_estimation(self):
        pts = {'depart_lat': DEP['lat'], 'depart_lng': DEP['lng'], 'arrivee_lat': ARR['lat'], 'arrivee_lng': ARR['lng']}
        e = self.client.post(API + 'estimation/', pts, format='json').json()['estimations'][0]
        self.assertIn('compteur', e['mention_prix'])
        self.assertEqual(e['trace'], [])  # sans clé Google

    def test_zone_non_couverte(self):
        loin = {'lat': 9.55, 'lng': 1.19, 'adresse': 'Kara'}  # hors Grand Lomé
        with self.assertRaises(S.ErreurCourse) as e:
            S.commander(self.user, self.moto, DEP, loin)
        self.assertEqual(e.exception.message, 'Zone non couverte')
        self.assertTrue(self.client.get(API + 'zone/', {'lat': DEP['lat'], 'lng': DEP['lng']}).json()['couverte'])
        self.assertFalse(self.client.get(API + 'zone/', {'lat': 9.55, 'lng': 1.19}).json()['couverte'])

    def test_coursiers_proches_sans_identite(self):
        partenaire(self.moto, 1, quand=timezone.now())
        partenaire(self.moto, 2, quand=timezone.now())
        partenaire(self.moto, 9, quand=timezone.now())  # hors rayon de 5 km
        self.client.force_authenticate(self.user)
        d = self.client.get(API + 'proches/', {'lat': DEP['lat'], 'lng': DEP['lng'], 'categorie': self.moto.pk}).json()
        self.assertEqual(d['nombre'], 2)
        self.assertEqual(set(d['coursiers'][0]), {'type', 'lat', 'lng'})
        self.assertEqual(d['coursiers'][0]['type'], 'moto')
        self.assertGreaterEqual(d['arrivee_min'], 1)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(API + 'proches/', {'lat': 6.13, 'lng': 1.22}).status_code, 401)


@override_settings(STORAGES=STORAGES)
class RechercheTests(APITestCase):
    def test_aucun_coursier_message_et_compteur(self):
        moto = Categorie.objects.get(code='moto')
        user = compte()
        self.client.force_authenticate(user)
        c = S.commander(user, moto, DEP, ARR)
        d = self.client.get(f'{API}{c.pk}/').json()
        self.assertEqual(d['statut'], 'recherche')
        self.assertEqual(d['recherche']['secondes_max'], 120)
        self.assertEqual(d['code_depart'], '')  # code désactivé par défaut
        S.avancer(c.pk, timezone.now() + timedelta(seconds=121))
        d = self.client.get(f'{API}{c.pk}/').json()
        self.assertEqual(d['statut'], 'aucun_partenaire')
        self.assertIn('Aucun coursier disponible', d['message'])


@override_settings(STORAGES=STORAGES)
class PinEtReferenceTests(APITestCase):
    def setUp(self):
        self.moto = Categorie.objects.get(code='moto')
        self.user = compte()
        ajuster(self.user, 5000, "Test", compte('Admin'))
        self.client.force_authenticate(self.user)
        self.pts = {'depart_lat': DEP['lat'], 'depart_lng': DEP['lng'], 'arrivee_lat': ARR['lat'],
                    'arrivee_lng': ARR['lng'], 'categorie': self.moto.pk, 'moyen_paiement': 'portefeuille'}

    def test_reference_unique_sans_confusion(self):
        refs = {S.commander(compte(), self.moto, DEP, ARR).reference for _ in range(5)}
        self.assertEqual(len(refs), 5)
        for r in refs:
            self.assertRegex(r, r'^LX-[A-HJ-NP-Z2-9]{6}$')

    def test_pin_creation_verification_blocage(self):
        self.assertEqual(self.client.get('/api/mobile/v1/solde/').status_code, 200)  # pas encore de PIN
        r = self.client.post(API + 'pin/creer/', {'pin': '1234', 'confirmation': '1235'}, format='json')
        self.assertEqual(r.json()['code'], 'confirmation')
        r = self.client.post(API + 'pin/creer/', {'pin': '1234', 'confirmation': '1234'}, format='json')
        self.assertEqual(r.status_code, 201)
        from .models import PinSolde
        self.assertNotIn('1234', PinSolde.objects.get(user=self.user).pin_hash)
        self.assertEqual(self.client.get('/api/mobile/v1/solde/').json()['code'], 'pin_requis')
        # achat payé avec le solde : PIN demandé
        self.assertEqual(self.client.post('/api/mobile/v1/paiements/', {'moyen': 'solde', 'type': 'produit'},
                                          format='json').json()['code'], 'pin_requis')
        # course payée avec le solde : PAS de PIN ; on sait seulement si le solde suffit
        self.assertTrue(self.client.get(API + 'solde-suffisant/', {'montant': 700}).json()['suffisant'])
        self.assertFalse(self.client.get(API + 'solde-suffisant/', {'montant': 999999}).json()['suffisant'])
        r = self.client.post(API, self.pts, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        jeton = self.client.post(API + 'pin/verifier/', {'pin': '1234'}, format='json').json()['jeton']
        self.assertEqual(self.client.get('/api/mobile/v1/solde/', HTTP_X_PIN=jeton).status_code, 200)
        for _ in range(4):
            self.assertEqual(self.client.post(API + 'pin/verifier/', {'pin': '0000'}, format='json').json()['code'], 'pin_faux')
        self.assertEqual(self.client.post(API + 'pin/verifier/', {'pin': '0000'}, format='json').json()['code'], 'pin_bloque')
        self.assertEqual(self.client.post(API + 'pin/verifier/', {'pin': '1234'}, format='json').json()['code'], 'pin_bloque')

    def test_pin_oublie(self):
        from django.core import mail
        self.client.post(API + 'pin/creer/', {'pin': '1234', 'confirmation': '1234'}, format='json')
        self.assertEqual(self.client.post(API + 'pin/oublie/', format='json').status_code, 200)
        code = re.search(r'(\d{6})', mail.outbox[-1].body).group(1)
        r = self.client.post(API + 'pin/reinitialiser/', {'code': '000000', 'pin': '5678', 'confirmation': '5678'}, format='json')
        self.assertEqual(r.json()['code'], 'code_invalide')
        r = self.client.post(API + 'pin/reinitialiser/', {'code': code, 'pin': '5678', 'confirmation': '5678'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('jeton', self.client.post(API + 'pin/verifier/', {'pin': '5678'}, format='json').json())

    def test_annulation_motif_visible_et_signalement(self):
        c = self.client.post(API, {**self.pts, 'moyen_paiement': 'especes'}, format='json').json()
        r = self.client.post(f"{API}{c['id']}/annuler/", {'frais': 0, 'motif': 'Trop long'}, format='json').json()
        self.assertEqual(r['annulations'][0]['motif'], 'Trop long')
        self.assertEqual(r['annulations'][0]['par'], 'client')
        s = self.client.post(f"{API}{c['id']}/signaler/", {'motif': 'retard', 'commentaire': 'Long'}, format='json').json()
        self.assertIn('Merci beaucoup', s['detail'])
        self.assertEqual(s['reference'], c['reference'])
        d = self.client.get(f"{API}{c['id']}/").json()
        self.assertEqual(d['signalements'][0]['motif'], 'Retard important')


class PageApplicationPartenaireTests(TestCase):
    def test_page_et_version(self):
        import json
        import os
        import tempfile
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, override_settings(MEDIA_ROOT=d, STORAGES=STORAGES):
            self.assertEqual(self.client.get('/api/mobile/v1/version/partenaire/').status_code, 404)
            os.makedirs(os.path.join(d, 'app-partenaire'))
            with open(os.path.join(d, 'app-partenaire', 'version.json'), 'w') as fh:
                json.dump({'version': '1.0.2', 'build': 3, 'taille': 10}, fh)
            with open(os.path.join(d, 'app-partenaire', 'Lantante-Partenaire-1.0.2.apk'), 'wb') as fh:
                fh.write(b'0' * 2048)
            v = self.client.get('/api/mobile/v1/version/partenaire/').json()
            self.assertEqual((v['version'], v['build']), ('1.0.2', 3))
            self.assertTrue(v['url_apk'].endswith('/app-partenaire/Lantante-Partenaire-1.0.2.apk'))
            r = self.client.get('/application/partenaire/')
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, 'Lantante Partenaire')
            self.assertContains(r, 'version 1.0.2')
            t = self.client.get('/application/partenaire/telecharger/')
            self.assertEqual(t.status_code, 200)
            self.assertIn('Lantante-Partenaire.apk', t['Content-Disposition'])
            t.close()



@override_settings(STORAGES=STORAGES)
class FavorisTests(APITestCase):
    def test_favori_servi_en_premier_et_api(self):
        moto = Categorie.objects.get(code='moto')
        client = compte()
        proche = partenaire(moto, 0.3, quand=timezone.now())
        favori = partenaire(moto, 4, quand=timezone.now())  # plus loin, mais favori
        # 1re course : le plus proche accepte, le client le met en favori via l'API
        c1 = S.commander(client, moto, DEP, ARR)
        S.accepter(proche, S.offre_en_cours(proche).pk)
        S.annuler_par_admin(Course.objects.get(pk=c1.pk), compte('Admin'))
        Course.objects.filter(pk=c1.pk).update(partenaire=favori)
        self.client.force_authenticate(client)
        self.assertEqual(self.client.post(f'{API}{c1.pk}/favori/').json(), {'favori': True})
        fav = self.client.get(API + 'favoris/').json()['resultats']
        self.assertEqual(fav[0]['id'], favori.pk)
        d = self.client.get(API + 'proches/', {'lat': DEP['lat'], 'lng': DEP['lng'], 'categorie': moto.pk}).json()
        self.assertEqual((d['nombre'], d['favoris']), (2, 1))
        # 2e course : l'offre va d'abord au favori
        c2 = S.commander(client, moto, DEP, ARR)
        self.assertEqual(c2.offres.get().partenaire, favori)
        self.client.force_authenticate(favori.user)
        o = self.client.post(API + 'partenaire/offre/', format='json').json()
        self.assertTrue(o['offre']['course']['favori'])
        # désactivé dans les Paramètres : ordre normal
        Parametres.objects.filter(pk=1).update(favoris_prioritaires=False)
        S.annuler_par_admin(c2, compte('Admin2'))
        c3 = S.commander(client, moto, DEP, ARR)
        self.assertEqual(c3.offres.get().partenaire, proche)
        self.client.force_authenticate(client)
        self.assertEqual(self.client.delete(f'{API}favoris/{favori.pk}/').json(), {'favori': False})



@override_settings(STORAGES=STORAGES)
class ProfilCoursierTests(APITestCase):
    """Un seul véhicule par coursier ; « Compléter mon profil » puis « Envoyer pour validation »."""

    def setUp(self):
        import tempfile
        from django.core.files.storage import FileSystemStorage
        from .models import DocumentPartenaire
        champ = DocumentPartenaire._meta.get_field('fichier')
        self._dossier = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        ancien, champ.storage = champ.storage, FileSystemStorage(location=self._dossier.name)
        self.addCleanup(setattr, champ, 'storage', ancien)
        self.addCleanup(self._dossier.cleanup)
        self.u = compte('Kossi')
        self.client.force_authenticate(self.u)

    def _piece(self, type_, **extra):
        from django.core.files.uploadedfile import SimpleUploadedFile
        # JPEG minimal (en-tête suffisant pour la vérification du type)
        jpg = SimpleUploadedFile('p.jpg', bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b'0' * 200, content_type='image/jpeg')
        return self.client.post(API + 'partenaire/documents/', {'type': type_, 'fichier': jpg, **extra},
                                format='multipart')

    def test_un_seul_vehicule(self):
        moto, voiture = Categorie.objects.get(code='moto'), Categorie.objects.get(code='voiture-non-climatisee')
        r = self.client.post(API + 'partenaire/', {'type': 'coursier', 'categories': [moto.pk, voiture.pk]},
                             format='json')
        self.assertEqual(r.json()['code'], 'un_seul_vehicule')
        r = self.client.post(API + 'partenaire/', {'type_vehicule': 'voiture', 'climatise': True}, format='json')
        self.assertEqual({c['code'] for c in r.json()['categories']}, {'voiture-non-climatisee', 'voiture-climatisee'})
        self.assertEqual(self.client.post(API + 'partenaire/', {'type_vehicule': 'avion'}, format='json').json()['code'],
                         'vehicule')
        # validé : changer de véhicule passe par une demande
        Partenaire.objects.filter(user=self.u).update(statut='valide')
        r = self.client.post(API + 'partenaire/', {'type_vehicule': 'moto'}, format='json')
        self.assertEqual(r.json()['code'], 'changement_vehicule')
        r = self.client.post(API + 'partenaire/changement-type/', {'vehicule': 'moto'}, format='json')
        self.assertIn(r.status_code, (200, 201))
        from .models import DemandeChangementType
        self.assertEqual(DemandeChangementType.objects.get().vehicule_demande, 'moto')

    def test_completer_puis_envoyer(self):
        r = self.client.post(API + 'partenaire/', {
            'type': 'coursier', 'type_vehicule': 'moto', 'marque': 'Haojue', 'modele': 'HJ125', 'couleur': 'Rouge',
            'annee': '2021', 'plaque': 'TG 1234 AB', 'telephone': '90000000', 'mobile_money': '90000000',
            'quartier': 'Bè', 'urgence_nom': 'Afi', 'urgence_tel': '91000000', 'date_naissance': '1995-04-02'},
            format='json')
        self.assertEqual(r.json()['annee'], 2021)
        self.assertEqual(r.json()['date_naissance'], '1995-04-02')
        self.assertIn('selfie', r.json()['manquants'])
        self.assertNotIn('photo_interieur', r.json()['manquants'])  # seulement pour une voiture
        r = self.client.post(API + 'partenaire/envoyer/')
        self.assertEqual(r.json()['code'], 'incomplet')
        self.assertEqual(self._piece('assurance').json()['code'], 'expiration')
        for t in ('selfie', 'identite_recto', 'identite_verso', 'permis_recto', 'permis_verso', 'carte_grise',
                  'photo_avant', 'photo_arriere', 'photo_cote'):
            self.assertEqual(self._piece(t).status_code, 201, t)
        self._piece('selfie')  # remplace l'ancienne, pas de doublon
        r = self._piece('assurance', expiration='2027-12-31')
        self.assertEqual(r.json()['manquants'], [])
        self.assertEqual(len([d for d in r.json()['documents'] if d['type'] == 'selfie']), 1)
        r = self.client.post(API + 'partenaire/envoyer/')
        self.assertEqual(r.json()['statut'], 'en_attente')
        # pas en ligne avant la validation
        r = self.client.post(API + 'partenaire/statut/', {'en_ligne': True, 'lat': 6.13, 'lng': 1.22}, format='json')
        self.assertEqual(r.json()['code'], 'non_valide')


class CategoriesParDefautTests(TestCase):
    def test_valider_donne_les_categories_du_vehicule(self):
        from django.contrib.admin.sites import site
        from .admin import PartenaireAdmin
        p = Partenaire.objects.create(user=compte('Yao'), type_vehicule='moto', statut='en_attente')
        self.assertFalse(p.categories.exists())
        adm = PartenaireAdmin(Partenaire, site)
        adm.message_user = lambda *a, **k: None
        adm.valider(None, Partenaire.objects.filter(pk=p.pk))
        self.assertEqual(list(p.categories.values_list('code', flat=True)), ['moto'])



@override_settings(STORAGES=STORAGES)
class CourseEnDirectTests(APITestCase):
    """Arrivée automatique, itinéraire, changement de paiement, pourboire, commission notifiée, gains."""

    def setUp(self):
        from Payments.solde import ajuster
        self.moto = Categorie.objects.get(code='moto')
        self.u = compte('Ama')
        ajuster(self.u, 5000, 'Test', None)
        self.p = partenaire(self.moto, 0.5, quand=timezone.now())
        self.c = S.commander(self.u, self.moto, {**DEP, 'adresse': 'Bè'}, {**ARR, 'adresse': 'Tokoin'})
        o = OffreCourse.objects.get(course=self.c)
        S.accepter(self.p, o.pk)

    def _position(self, lat, lng):
        Partenaire.objects.filter(pk=self.p.pk).update(lat=lat, lng=lng, position_le=timezone.now())
        self.p.refresh_from_db()

    def test_arrivee_auto_et_bouton_selon_distance(self):
        self.assertEqual(S.arrivee_automatique(self.p), None)  # 500 m : rien
        with self.assertRaises(S.ErreurCourse) as e:
            S.signaler_arrivee(self.p, self.c.pk)
        self.assertEqual(e.exception.code, 'trop_loin')
        self._position(DEP['lat'] - 0.001, DEP['lng'])  # ~110 m : bouton permis
        self.assertEqual(S.signaler_arrivee(self.p, self.c.pk).statut, 'arrive')

    def test_arrivee_automatique_a_quelques_metres(self):
        self._position(DEP['lat'] - 0.0002, DEP['lng'])  # ~22 m
        c = S.arrivee_automatique(self.p)
        self.assertEqual(c.statut, 'arrive')
        self.assertIn('arrivé', c.messages.filter(par='systeme').last().texte.lower())

    def test_itineraire_client_et_coursier(self):
        trace = {'km': 0.6, 'minutes': 2, 'trace': [[6.1, 1.2], [6.11, 1.21]]}
        with mock.patch('courses.carto.trace_route', return_value=trace):
            self.client.force_authenticate(self.u)
            r = self.client.get(f'{API}{self.c.pk}/itineraire/').json()
            self.assertEqual(r['cible'], 'depart')
            self.assertEqual(len(r['trace']), 2)
            self.assertGreater(r['distance_depart_m'], 400)
            self.client.force_authenticate(self.p.user)
            self.assertEqual(self.client.get(f'{API}{self.c.pk}/itineraire/').status_code, 200)
            self.client.force_authenticate(compte('Autre'))
            self.assertEqual(self.client.get(f'{API}{self.c.pk}/itineraire/').status_code, 404)

    def test_changer_paiement_puis_pourboire_et_commission(self):
        self.client.force_authenticate(self.u)
        total = Course.objects.get(pk=self.c.pk).total_client
        r = self.client.post(f'{API}{self.c.pk}/paiement/', {'moyen': 'portefeuille'}, format='json').json()
        self.assertEqual(r['moyen_paiement'], 'portefeuille')
        self.assertEqual(portefeuille(self.u).solde, 5000 - total)
        r = self.client.post(f'{API}{self.c.pk}/paiement/', {'moyen': 'especes'}, format='json').json()
        self.assertEqual(r['moyen_paiement'], 'especes')
        self.assertEqual(portefeuille(self.u).solde, 5000)
        S.signaler_arrivee(self.p, self.c.pk, verifier_distance=False)
        S.demarrer(self.p, self.c.pk, '')
        S.terminer(self.p, self.c.pk)
        from api_mobile.models import Notification
        n = Notification.objects.filter(utilisateur=self.p.user, titre='Commission Lantante').first()
        self.assertIsNotNone(n)
        self.assertIn('Commission 15 %', n.message)
        self.assertEqual(self.client.post(f'{API}{self.c.pk}/paiement/', {'moyen': 'portefeuille'},
                                          format='json').json()['code'], 'etape')
        r = self.client.post(f'{API}{self.c.pk}/noter/', {'note': 5, 'pourboire': 600}, format='json').json()
        self.assertEqual(r['code'], 'pourboire')  # 500 maximum
        solde_avant = Partenaire.objects.get(pk=self.p.pk).solde
        self.assertEqual(self.client.post(f'{API}{self.c.pk}/noter/', {'note': 5, 'pourboire': 300},
                                          format='json').json(), {'ok': True})
        self.assertEqual(Partenaire.objects.get(pk=self.p.pk).solde, solde_avant + 300)
        self.assertEqual(portefeuille(self.u).solde, 4700)
        # gains du coursier : aujourd'hui, avec le pourboire
        self.client.force_authenticate(self.p.user)
        with mock.patch('courses.pin.exige_pin', return_value=None):
            g = self.client.get(API + 'partenaire/solde/').json()['gains']
        c = Course.objects.get(pk=self.c.pk)
        self.assertEqual(g['jour']['courses'], 1)
        self.assertEqual(g['jour']['gain'], c.prix_final - c.detail_prix['commission'] + 300)
        r = self.client.get(API + 'partenaire/courses/?jour=aujourdhui').json()
        self.assertEqual(len(r['resultats']), 1)


class PhotoProfilTests(APITestCase):
    def test_photo_facultative_du_client(self):
        import tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, \
                override_settings(MEDIA_ROOT=d, STORAGES=STORAGES):
            u = compte('Ama')
            self.client.force_authenticate(u)
            self.assertEqual(self.client.post('/api/mobile/v1/me/photo/', {}, format='multipart').json()['code'], 'photo')
            img = SimpleUploadedFile('moi.jpg', bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b'0' * 100, content_type='image/jpeg')
            r = self.client.post('/api/mobile/v1/me/photo/', {'photo': img}, format='multipart').json()
            self.assertIn('avatars/', r['photo'])
            r = self.client.delete('/api/mobile/v1/me/photo/').json()
            self.assertFalse(r['photo'])


class MessageFinTests(CourseEnDirectTests):
    def test_merci_a_la_fin(self):
        S.signaler_arrivee(self.p, self.c.pk, verifier_distance=False)
        S.demarrer(self.p, self.c.pk, '')
        c = S.terminer(self.p, self.c.pk)
        texte = c.messages.filter(par='systeme').last().texte
        self.assertIn('Merci Ama de nous avoir choisis', texte)
        self.assertIn('À très bientôt', texte)
        self.assertFalse(any(ord(ch) > 0x2000 for ch in texte))  # sans émojis


class AnnulationPortefeuilleTests(CourseEnDirectTests):
    def test_annuler_ne_garde_que_200(self):
        """Payée par le portefeuille, annulée après le délai de grâce : seuls 200 FCFA sont gardés, le reste est rendu."""
        self.client.force_authenticate(self.u)
        self.client.post(f'{API}{self.c.pk}/paiement/', {'moyen': 'portefeuille'}, format='json')
        plus_tard = timezone.now() + timedelta(minutes=2, seconds=30)  # après la grâce, coursier pas en retard
        c, frais = S.annuler_par_client(self.c.pk, self.u, motif='Plus besoin', maintenant=plus_tard)
        self.assertEqual(frais, 200)
        self.assertEqual(portefeuille(self.u).solde, 5000 - 200)
        # course démarrée : plus d'annulation possible

    def test_pas_d_annulation_apres_le_depart(self):
        S.signaler_arrivee(self.p, self.c.pk, verifier_distance=False)
        S.demarrer(self.p, self.c.pk, '')
        with self.assertRaises(S.ErreurCourse) as e:
            S.annuler_par_client(self.c.pk, self.u, motif='Plus besoin')
        self.assertEqual(e.exception.code, 'etape')


class RenvoiOffreTests(TestCase):
    def test_coursier_seul_recoit_a_nouveau_la_course(self):
        moto = Categorie.objects.get(code='moto')
        u = compte('Ama')
        p = partenaire(moto, 0.5, quand=JOUR)
        with mock.patch('django.utils.timezone.now', return_value=JOUR):
            c = S.commander(u, moto, DEP, ARR)
        o1 = OffreCourse.objects.get(course=c)
        o1.recue_le = JOUR
        o1.save(update_fields=['recue_le'])
        t = JOUR + timedelta(seconds=11)  # 10 s passées sans réponse
        Partenaire.objects.filter(pk=p.pk).update(position_le=t)
        S.avancer(c.pk, t)
        offres = list(OffreCourse.objects.filter(course=c).order_by('envoyee_le'))
        self.assertEqual(len(offres), 2)
        self.assertEqual(offres[0].reponse, 'ignoree')
        self.assertEqual(offres[1].partenaire_id, p.pk)  # la même course lui est renvoyée
        self.assertEqual(offres[1].reponse, 'en_attente')

    def test_jamais_renvoyee_apres_un_refus(self):
        moto = Categorie.objects.get(code='moto')
        u = compte('Ama')
        p = partenaire(moto, 0.5, quand=JOUR)
        with mock.patch('django.utils.timezone.now', return_value=JOUR):
            c = S.commander(u, moto, DEP, ARR)
        o1 = OffreCourse.objects.get(course=c)
        S.refuser(p, o1.pk, JOUR + timedelta(seconds=2))
        Partenaire.objects.filter(pk=p.pk).update(position_le=JOUR + timedelta(seconds=3))
        S.avancer(c.pk, JOUR + timedelta(seconds=3))
        self.assertEqual(OffreCourse.objects.filter(course=c).count(), 1)


@override_settings(STORAGES=STORAGES)
class FactureTests(CourseEnDirectTests):
    def test_facture_pdf_et_prix_sans_minutes(self):
        self.assertEqual(self.moto.prix_min, 0)
        S.signaler_arrivee(self.p, self.c.pk, verifier_distance=False)
        S.demarrer(self.p, self.c.pk, '')
        Course.objects.filter(pk=self.c.pk).update(distance_reelle_km=3, demarree_le=timezone.now() - timedelta(minutes=40))
        c = S.terminer(self.p, self.c.pk)
        m = Categorie.objects.get(code='moto')
        attendu = S.arrondi_sup(max(m.minimum, m.prise_en_charge + 3 * m.prix_km), Parametres.get().arrondi)
        self.assertEqual(c.prix_final, attendu)  # 40 minutes ne coûtent rien de plus
        self.client.force_authenticate(self.u)
        r = self.client.get(f'{API}{c.pk}/facture.pdf')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
