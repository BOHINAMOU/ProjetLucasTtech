from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import ChampInscription, InscriptionService, Service

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'


@override_settings(STORAGES=STORAGES)
class InscriptionServiceTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(email='a@example.com', password='x-Pass-12345')
        self.s = Service.objects.create(admin=self.admin, title='Création de compte', description='x',
                                        inscriptions_ouvertes=True)
        self.nom = ChampInscription.objects.create(service=self.s, libelle='Nom complet', ordre=1)
        self.tel = ChampInscription.objects.create(service=self.s, libelle='Téléphone', type='telephone', ordre=2)
        self.choix = ChampInscription.objects.create(service=self.s, libelle='Formule', type='choix',
                                                     choix='Simple, Pro', obligatoire=False, ordre=3)

    def test_formulaire_et_inscription(self):
        d = self.client.get(f'{API}services/{self.s.pk}/').json()
        self.assertTrue(d['inscription']['ouverte'])
        self.assertEqual([c['libelle'] for c in d['inscription']['champs']], ['Nom complet', 'Téléphone', 'Formule'])
        self.assertEqual(d['inscription']['champs'][2]['choix'], ['Simple', 'Pro'])
        r = self.client.post(f'{API}services/{self.s.pk}/inscription/',
                             {'reponses': {str(self.tel.pk): 'abc', str(self.choix.pk): 'Autre'}}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()['erreurs']), {str(self.nom.pk), str(self.tel.pk), str(self.choix.pk)})
        r = self.client.post(f'{API}services/{self.s.pk}/inscription/',
                             {'reponses': {str(self.nom.pk): 'Ama Koffi', str(self.tel.pk): '90 00 00 00',
                                           str(self.choix.pk): 'Pro'}}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(InscriptionService.objects.get().reponses,
                         {'Nom complet': 'Ama Koffi', 'Téléphone': '+22890000000', 'Formule': 'Pro'})

    def test_cloture_et_export(self):
        self.client.force_login(self.admin)
        self.client.post('/lantanteAdminTech/Services/service/', {'action': 'cloturer', '_selected_action': [self.s.pk]})
        self.s.refresh_from_db()
        self.assertFalse(self.s.inscriptions_ouvertes)
        r = self.client.post(f'{API}services/{self.s.pk}/inscription/', {'reponses': {}}, format='json')
        self.assertEqual(r.status_code, 400)
        InscriptionService.objects.create(service=self.s, reponses={'Nom complet': 'Ama'})
        r = self.client.post('/lantanteAdminTech/Services/inscriptionservice/',
                             {'action': 'exporter_excel',
                              '_selected_action': list(InscriptionService.objects.values_list('pk', flat=True))})
        self.assertIn('spreadsheetml', r['Content-Type'])
