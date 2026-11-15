from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Ecole, Filiere, MembreEcole, PhotoEcole

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'
A = '/lantanteAdminTech/'


@override_settings(STORAGES=STORAGES)
class EcolesTests(APITestCase):
    def setUp(self):
        U = get_user_model()
        self.e = Ecole.objects.create(nom='Lycée de Tokoin', type='lycee', ville='Lomé')
        self.autre = Ecole.objects.create(nom='Université de Kara', type='universite', ville='Kara')
        self.f = Filiere.objects.create(ecole=self.e, nom='Série D', frais=50000)
        self.resp = U.objects.create_user(email='resp@example.com', password='x-Pass-12345', is_verified=True)
        self.collab = U.objects.create_user(email='col@example.com', password='x-Pass-12345', is_verified=True)
        MembreEcole.objects.create(ecole=self.e, user=self.resp, role='proprietaire')
        MembreEcole.objects.create(ecole=self.e, user=self.collab)

    def test_api_liste_fiche_filieres_et_lien_d_inscription(self):
        self.e.site_web = 'https://tokoin.example.tg'
        self.e.adresse = 'Tokoin, Lomé'
        self.e.save()
        self.f.resume, self.f.debouches, self.f.conditions, self.f.duree = 'Sciences', 'Médecine, ingénierie', 'BEPC', '3 ans'
        self.f.save()
        PhotoEcole.objects.create(ecole=self.e, image='ecoles/photos/a.jpg', legende='La cour')
        d = self.client.get(API + 'ecoles/?type=lycee').json()
        d = d['resultats'] if isinstance(d, dict) else d
        self.assertEqual([x['nom'] for x in d], ['Lycée de Tokoin'])
        self.assertEqual(d[0]['lien_inscription'], 'https://tokoin.example.tg')  # pas de lien dédié : le site web
        f = self.client.get(f'{API}ecoles/{self.e.slug}/').json()
        self.assertEqual(f['adresse'], 'Tokoin, Lomé')
        self.assertEqual(f['photos'][0]['legende'], 'La cour')
        fil = f['filieres'][0]
        self.assertEqual((fil['nom'], fil['resume'], fil['duree'], fil['conditions']), ('Série D', 'Sciences', '3 ans', 'BEPC'))
        self.assertIn('Médecine', fil['debouches'])
        self.e.lien_inscription = 'https://tokoin.example.tg/inscription'
        self.e.save()
        self.assertEqual(self.client.get(f'{API}ecoles/{self.e.slug}/').json()['lien_inscription'],
                         'https://tokoin.example.tg/inscription')
        self.assertEqual(self.client.get(f'{API}ecoles/{self.autre.slug}/').json()['lien_inscription'], '')  # pas de bouton
        self.assertEqual(self.client.post(f'{API}ecoles/{self.e.slug}/inscription/', {'nom': 'X'}).status_code, 404)
        self.assertEqual(self.client.get(API + 'recherche/?q=tokoin').json()['groupes'][0]['type'], 'ecole')

    def test_espace_de_l_ecole_limite_a_son_ecole(self):
        self.resp.refresh_from_db()
        self.assertTrue(self.resp.is_staff)
        self.client.force_login(self.collab)
        r = self.client.get(A + 'Ecoles/ecole/')
        self.assertContains(r, 'Lycée de Tokoin')
        self.assertNotContains(r, 'Université de Kara')
        self.assertEqual(self.client.get(f'{A}Ecoles/ecole/{self.autre.pk}/change/').status_code, 302)
        self.assertContains(self.client.get(f'{A}Ecoles/ecole/{self.e.pk}/change/'), 'lien_inscription')

    def test_seul_le_responsable_gere_l_equipe(self):
        from .admin import MembreInline
        from django.contrib.admin.sites import site
        from django.test import RequestFactory
        rq = RequestFactory().get('/')
        rq.user = self.collab
        self.assertFalse(MembreInline(Ecole, site).has_add_permission(rq, self.e))
        rq.user = self.resp
        self.assertTrue(MembreInline(Ecole, site).has_add_permission(rq, self.e))
