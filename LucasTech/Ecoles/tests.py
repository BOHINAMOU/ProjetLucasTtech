from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Ecole, Filiere, InscriptionEcole, MembreEcole

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

    def test_api_liste_fiche_et_inscription(self):
        d = self.client.get(API + 'ecoles/?type=lycee').json()
        d = d['resultats'] if isinstance(d, dict) else d
        self.assertEqual([x['nom'] for x in d], ['Lycée de Tokoin'])
        f = self.client.get(f'{API}ecoles/{self.e.slug}/').json()
        self.assertEqual(f['filieres'][0]['nom'], 'Série D')
        r = self.client.post(f'{API}ecoles/{self.e.slug}/inscription/',
                             {'nom': 'Koffi', 'prenom': 'Ama', 'telephone': '90 00 00 00', 'filiere': self.f.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(InscriptionEcole.objects.get().telephone, '+22890000000')
        r = self.client.post(f'{API}ecoles/{self.e.slug}/inscription/',
                             {'nom': 'K', 'prenom': 'Ama2', 'telephone': 'abc'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()['erreurs']), {'nom', 'prenom', 'telephone'})
        self.assertEqual(self.client.get(API + 'recherche/?q=tokoin').json()['groupes'][0]['type'], 'ecole')

    def test_espace_de_l_ecole_limite_a_son_ecole(self):
        self.resp.refresh_from_db()
        self.assertTrue(self.resp.is_staff)
        InscriptionEcole.objects.create(ecole=self.e, nom='Koffi', prenom='Ama', telephone='+22890000000')
        InscriptionEcole.objects.create(ecole=self.autre, nom='Mensah', prenom='Yao', telephone='+22891000000')
        self.client.force_login(self.collab)
        r = self.client.get(A + 'Ecoles/ecole/')
        self.assertContains(r, 'Lycée de Tokoin')
        self.assertNotContains(r, 'Université de Kara')
        r = self.client.get(A + 'Ecoles/inscriptionecole/')
        self.assertContains(r, 'Koffi')
        self.assertNotContains(r, 'Mensah')
        self.assertEqual(self.client.get(f'{A}Ecoles/ecole/{self.autre.pk}/change/').status_code, 302)
        r = self.client.post(A + 'Ecoles/inscriptionecole/',
                             {'action': 'exporter_excel', '_selected_action': list(InscriptionEcole.objects.values_list('pk', flat=True))})
        self.assertIn('spreadsheetml', r['Content-Type'])

    def test_seul_le_responsable_gere_l_equipe(self):
        from .admin import MembreInline
        from django.contrib.admin.sites import site
        from django.test import RequestFactory
        rq = RequestFactory().get('/')
        rq.user = self.collab
        self.assertFalse(MembreInline(Ecole, site).has_add_permission(rq, self.e))
        rq.user = self.resp
        self.assertTrue(MembreInline(Ecole, site).has_add_permission(rq, self.e))
