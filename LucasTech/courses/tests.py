"""Lantante Express : prix, affectation (ordre par distance, 10 s, verrou), portefeuille, annulation, API."""
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
        brut = 150 + km * 100 + mn * 10
        self.assertEqual(e['prix'], 700)                                # 150 + 433,7 + 110 = 693,7 → 700
        self.assertEqual(e['prix'] % 50, 0)
        self.assertGreaterEqual(e['prix'], brut)
        self.assertEqual(e['total'], 700)

    def test_minimum(self):
        e = S.estimer(self.clim, DEP['lat'], DEP['lng'], DEP['lat'] + 0.001, DEP['lng'], quand=JOUR)
        self.assertEqual(e['prix'], 1000)
        self.assertTrue(e['minimum_applique'])

    def test_coefficient_de_nuit(self):
        jour = S.estimer(self.moto, DEP['lat'], DEP['lng'], ARR['lat'], ARR['lng'], quand=JOUR)['prix']
        nuit = S.estimer(self.moto, DEP['lat'], DEP['lng'], ARR['lat'], ARR['lng'], quand=NUIT)
        self.assertEqual(nuit['coefficient'], 1.25)
        self.assertEqual(nuit['prix'], S.arrondi_sup(693.7 * 1.25, 50))  # 867 → 900
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
        self.assertEqual(c.offres.get().reponse, 'ignoree')

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
        for i in range(3):
            with mock.patch('django.utils.timezone.now', return_value=t):
                c = S.commander(compte(), self.moto, DEP, ARR)
            S.offre_en_cours(p, t + timedelta(seconds=1))
            S.avancer(c.pk, t + timedelta(seconds=12))
            Partenaire.objects.filter(pk=p.pk).update(position_le=t + timedelta(seconds=12))
            t += timedelta(seconds=13)
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

    def test_reservation_puis_debit_reel(self):
        c, p = self._acceptee()
        self.assertEqual(portefeuille(self.client_user).solde, 5000 - 700)
        self.assertEqual(c.montant_reserve, 700)
        S.demarrer(p, c.pk, c.code_depart, JOUR + timedelta(minutes=5))
        c = S.terminer(p, c.pk, JOUR + timedelta(minutes=20))
        self.assertEqual(portefeuille(self.client_user).solde, 4300)
        self.assertRegex(c.numero_recu, r'^LE-2026-\d{6}$')
        p.refresh_from_db()
        self.assertEqual(p.solde, 700 - 105)  # gain net (commission 15 %)

    def test_attente_payante(self):
        c, p = self._acceptee()
        S.signaler_arrivee(p, c.pk, JOUR + timedelta(minutes=5))
        S.demarrer(p, c.pk, c.code_depart, JOUR + timedelta(minutes=10))  # 5 min, dont 3 gratuites
        c = S.terminer(p, c.pk, JOUR + timedelta(minutes=25))
        self.assertEqual(c.prix_final, 750)  # 700 + 2 × 25
        self.assertEqual(portefeuille(self.client_user).solde, 4250)

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
        self.assertEqual(portefeuille(self.client_user).solde, 4300)
        S.annuler_par_client(c.pk, self.client_user, frais_acceptes=0, maintenant=JOUR + timedelta(seconds=5))
        self.assertEqual(portefeuille(self.client_user).solde, 5000)

    def test_annulation_apres_grace_avec_frais(self):
        c, p = self._acceptee()
        t = JOUR + timedelta(minutes=3)
        self.assertEqual(S.frais_annulation_client(c, t), (200, 'apres_grace'))
        with self.assertRaises(S.ErreurCourse):
            S.annuler_par_client(c.pk, self.client_user, frais_acceptes=0, maintenant=t)  # frais pas vus
        S.annuler_par_client(c.pk, self.client_user, frais_acceptes=200, maintenant=t)
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
        S.annuler_par_client(c.pk, self.client_user, frais_acceptes=200, maintenant=t)
        self.assertEqual(Annulation.objects.get(course=c).frais_regles, False)
        self.assertEqual(S.frais_reportes(self.client_user), 200)
        # course suivante en espèces : frais ajoutés, commission en dette
        p2 = partenaire(self.moto, 0.3, quand=t)
        with mock.patch('django.utils.timezone.now', return_value=t):
            c2 = S.commander(self.client_user, self.moto, DEP, ARR)
        self.assertEqual(c2.total_client, 900)
        o = S.offre_en_cours(p2, t + timedelta(seconds=1))
        S.accepter(p2, o.pk, t + timedelta(seconds=2))
        S.demarrer(p2, c2.pk, Course.objects.get(pk=c2.pk).code_depart, t + timedelta(minutes=4))
        S.terminer(p2, c2.pk, t + timedelta(minutes=20))
        p2.refresh_from_db()
        self.assertEqual(p2.solde, -105 - 200)  # commission + frais encaissés pour Lantante
        self.assertEqual(S.frais_reportes(self.client_user), 0)

    def test_annulation_par_partenaire_relance(self):
        c, p = self._acceptee()
        autre = partenaire(self.moto, 2, quand=JOUR + timedelta(seconds=10))
        with mock.patch('django.utils.timezone.now', return_value=JOUR + timedelta(seconds=10)):
            S.annuler_par_partenaire(p, c.pk, 'Panne', maintenant=JOUR + timedelta(seconds=10))
        c.refresh_from_db()
        self.assertEqual(c.statut, 'recherche')
        self.assertEqual(c.offres.filter(reponse='en_attente').get().partenaire, autre)
        self.assertEqual(c.montant_reserve, 700)  # toujours réservé, même prix

    def test_remboursement_retenu_sur_partenaire(self):
        c, p = self._acceptee()
        S.demarrer(p, c.pk, c.code_depart, JOUR + timedelta(minutes=5))
        c = S.terminer(p, c.pk, JOUR + timedelta(minutes=20))
        r = S.demander_remboursement(c, 300, 300, "Mauvais trajet", self.admin)
        self.assertEqual(r.statut, 'valide')
        self.assertEqual(portefeuille(self.client_user).solde, 4600)
        p.refresh_from_db()
        self.assertEqual(p.solde, 595 - 300)
        gros = S.demander_remboursement(c, 6000, 0, "Geste", self.admin)
        self.assertEqual(gros.statut, 'en_attente')  # au-delà de 5 000 : second admin
        with self.assertRaises(S.ErreurCourse):
            S.valider_remboursement(gros, self.admin)
        S.valider_remboursement(gros, compte('Second'))
        self.assertEqual(portefeuille(self.client_user).solde, 10600)

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
        self.assertEqual([s['code'] for s in d['services']], ['moto', 'voiture', 'cargo'])
        voiture = d['services'][1]['categories']
        self.assertEqual([c['active'] for c in voiture], [True, True, False])  # Prestige : bientôt
        pts = {'depart_lat': DEP['lat'], 'depart_lng': DEP['lng'], 'arrivee_lat': ARR['lat'], 'arrivee_lng': ARR['lng']}
        e = self.client.post(API + 'estimation/', pts, format='json').json()
        self.assertEqual(len(e['estimations']), 3)  # catégories actives seulement
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
        self.assertEqual(r.json()['statut'], 'annulee')
        self.assertEqual(len(self.client.get(API).json()['resultats']), 1)

    def test_parcours_partenaire(self):
        coursier = compte('Kodjo')
        self.client.force_authenticate(coursier)
        self.assertEqual(self.client.get(API + 'partenaire/').status_code, 404)
        r = self.client.post(API + 'partenaire/', {'type': 'coursier', 'plaque': 'TG 1234 AB', 'vehicule': 'Haojue'},
                             format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual({c['service'] for c in r.json()['categories']}, {'moto', 'voiture'})
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
        self.assertEqual(self.client.post(base + 'arrive/').json()['statut'], 'arrive')
        self.assertEqual(self.client.post(base + 'demarrer/', {'code': '----'}, format='json').json()['code'], 'code')
        self.assertEqual(self.client.post(base + 'demarrer/', {'code': c['code_depart']}, format='json').status_code, 200)
        self.assertEqual(self.client.post(base + 'terminer/').json()['statut'], 'terminee')
        s = self.client.get(API + 'partenaire/solde/').json()
        self.assertEqual(s['solde'], -105)
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
        self.assertIn('Haojue rouge, TG 1234 AB', auto['texte'])
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
        self.assertGreater(c.prix_final, c.prix_estime)
        sup = c.detail_prix['supplements']
        self.assertTrue(sup and sup[0]['motif'].startswith('Trajet plus long'))
        rc = self.client.force_authenticate(self.user) or self.client.get(f'{API}{c.pk}/recu/').json()
        self.assertEqual(rc['prix_annonce'], c.prix_estime)
        self.assertEqual(len(rc['supplements']), 1)

    def test_petit_detour_sans_augmentation(self):
        c, p = self._en_cours()
        lat = DEP['lat']
        for _ in range(15):  # 15 × 220 m ≈ 3,3 km : sous la distance prévue + 15 %
            lat += 0.002
            S.suivre_position(p, lat, DEP['lng'])
        c = S.terminer(p, c.pk)
        self.assertEqual(c.prix_final, c.prix_estime)
        self.assertEqual(c.detail_prix['supplements'], [])

    def test_mention_dans_estimation(self):
        pts = {'depart_lat': DEP['lat'], 'depart_lng': DEP['lng'], 'arrivee_lat': ARR['lat'], 'arrivee_lng': ARR['lng']}
        e = self.client.post(API + 'estimation/', pts, format='json').json()['estimations'][0]
        self.assertIn('3 min', e['mention_prix'])
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
