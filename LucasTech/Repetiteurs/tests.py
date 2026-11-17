import os
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Repetiteur

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'


@override_settings(STORAGES=STORAGES)
class RepetiteursTests(APITestCase):
    def setUp(self):
        Repetiteur.objects.create(nom='Kossi Agbéko', matieres='Mathématiques, Physique-Chimie', ville='Lomé',
                                  quartier='Bè', whatsapp='+228 90 00 00 01', email='k@example.com', telephone='+22890000001',
                                  niveaux='3e, Tle', tarif='15 000 CFA / mois')
        Repetiteur.objects.create(nom='Afi Mensah', matieres='Anglais', ville='Kara')
        Repetiteur.objects.create(nom='Caché', matieres='SVT', ville='Lomé', actif=False)

    def test_liste_recherche_filtres_et_fiche(self):
        d = self.client.get(API + 'repetiteurs/').json()
        self.assertEqual([r['nom'] for r in d['resultats']], ['Afi Mensah', 'Kossi Agbéko'])
        self.assertEqual(d['matieres'], ['Anglais', 'Mathématiques', 'Physique-Chimie'])
        self.assertEqual(d['villes'], ['Kara', 'Lomé'])
        self.assertEqual([r['nom'] for r in self.client.get(API + 'repetiteurs/?q=physique').json()['resultats']],
                         ['Kossi Agbéko'])
        self.assertEqual(len(self.client.get(API + 'repetiteurs/?ville=Kara').json()['resultats']), 1)
        self.assertEqual(len(self.client.get(API + 'repetiteurs/?matiere=Anglais').json()['resultats']), 1)
        k = Repetiteur.objects.get(nom='Kossi Agbéko')
        f = self.client.get(f'{API}repetiteurs/{k.pk}/').json()
        self.assertEqual((f['whatsapp'], f['email'], f['telephone'], f['tarif']),
                         ('22890000001', 'k@example.com', '+22890000001', '15 000 CFA / mois'))
        cache = Repetiteur.objects.get(nom='Caché')
        self.assertEqual(self.client.get(f'{API}repetiteurs/{cache.pk}/').status_code, 404)

    def test_role_delegue(self):
        from core.models import Delegation
        u = get_user_model().objects.create_user(email='rep@example.com', password='x-Pass-12345', is_verified=True)
        Delegation.objects.create(user=u, type='repetiteurs')
        u.refresh_from_db()
        self.assertTrue(u.is_staff and u.has_perm('Repetiteurs.add_repetiteur'))
        self.client.force_login(u)
        self.assertContains(self.client.get('/lantanteAdminTech/Repetiteurs/repetiteur/'), 'Kossi')

    def test_formulaire_admin_simple_avec_carte(self):
        admin = get_user_model().objects.create_superuser(email='ad@example.com', password='x-Pass-12345')
        self.client.force_login(admin)
        r = self.client.get('/lantanteAdminTech/Repetiteurs/repetiteur/add/')
        self.assertContains(r, 'carte_produit.js')
        r = self.client.post('/lantanteAdminTech/Repetiteurs/repetiteur/add/', {
            'nom': 'Essai', 'matieres': 'Français', 'ville': 'Lomé', 'actif': 'on', 'ordre': 0, 'whatsapp': '90 12 34 56',
            'latitude': '6.130000', 'longitude': '1.220000'})
        self.assertEqual(r.status_code, 302, r.content[:500])
        self.assertTrue(Repetiteur.objects.filter(nom='Essai', latitude__isnull=False).exists())

    def test_charger_exemples_sans_doublon_puis_supprimer(self):
        from unittest import mock
        from django.core.management import call_command
        from Ecoles.models import Ecole
        with mock.patch('urllib.request.urlopen', side_effect=OSError('hors ligne')):
            call_command('charger_exemples', stdout=open(os.devnull, 'w'), stderr=open(os.devnull, 'w'))
            call_command('charger_exemples', stdout=open(os.devnull, 'w'), stderr=open(os.devnull, 'w'))
        self.assertEqual(Ecole.objects.filter(slug='ucao-uut').count(), 1)
        self.assertEqual(Ecole.objects.get(slug='ucao-uut').filieres.count(), 9)
        self.assertEqual(Repetiteur.objects.filter(est_exemple=True).count(), 5)
        r = self.client.get('/api/mobile/v1/repetiteurs/')
        self.assertTrue(all(x['exemple'] for x in r.json()['resultats'] if x['nom'].startswith('Exemple')))
        Repetiteur.objects.create(nom='Vrai', matieres='Maths', ville='Lomé')
        admin = get_user_model().objects.create_superuser(email='ad2@example.com', password='x-Pass-12345')
        self.client.force_login(admin)
        r = self.client.post('/lantanteAdminTech/Repetiteurs/repetiteur/', {'action': 'supprimer_exemples', 'index': 0})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Repetiteur.objects.filter(est_exemple=True).exists())
        self.assertTrue(Repetiteur.objects.filter(nom='Vrai').exists())


    def test_whatsapp_obligatoire_et_format(self):
        from django.core.exceptions import ValidationError
        from .models import whatsapp_togo
        self.assertEqual(whatsapp_togo('+228 90 12 34 56'), '22890123456')
        self.assertEqual(whatsapp_togo('90123456'), '22890123456')
        for faux in ('', '1234', '+33 6 12 34 56 78'):
            with self.assertRaises(ValidationError):
                whatsapp_togo(faux)
        r = Repetiteur(nom='Sans numéro', matieres='Maths', ville='Lomé')
        with self.assertRaises(ValidationError):
            r.full_clean()
        Repetiteur(nom='Exemple', matieres='Maths', ville='Lomé', est_exemple=True).full_clean()
