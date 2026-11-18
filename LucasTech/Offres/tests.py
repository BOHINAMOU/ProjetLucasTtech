import datetime
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import CandidatureEmploi, OffreEmploi

MEDIA = tempfile.mkdtemp()
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'


@override_settings(MEDIA_ROOT=MEDIA, STORAGES=STORAGES, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmploisTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)
        for f in Path(settings.PRIVATE_MEDIA_ROOT, 'emplois', 'cv').glob('cv*'):
            f.unlink(missing_ok=True)

    def setUp(self):
        cache.clear()
        self.u = get_user_model().objects.create_user(email='kofi@example.com', password='x-Pass-12345')
        self.c = APIClient()
        self.c.force_authenticate(self.u)
        self.a = OffreEmploi.objects.create(titre='Comptable', entreprise='Cabinet A', ville='Lomé', description='Tenue des comptes',
                                            created_at=timezone.now() - datetime.timedelta(days=1))
        self.b = OffreEmploi.objects.create(titre='Développeur web', entreprise='Société B', ville='Kara',
                                            type_contrat='stage', description='Django', whatsapp='+228 90 11 22 33')
        OffreEmploi.objects.create(titre='Expirée', entreprise='C', description='x',
                                   date_limite=timezone.localdate() - datetime.timedelta(days=1))

    def test_liste_non_lues_dabord_et_expirees_masquees(self):
        d = self.c.get(API + 'emplois/').json()
        self.assertEqual([o['titre'] for o in d['resultats']], ['Développeur web', 'Comptable'])
        self.assertEqual(d['non_lues'], 2)
        self.c.post(API + f'emplois/{self.b.pk}/lu/')
        d = self.c.get(API + 'emplois/').json()
        self.assertEqual([o['titre'] for o in d['resultats']], ['Comptable', 'Développeur web'])  # lue : en bas
        self.assertEqual(d['non_lues'], 1)
        self.assertEqual(self.c.get(API + 'emplois/', {'type': 'stage'}).json()['resultats'][0]['titre'], 'Développeur web')
        self.assertEqual(self.c.get(API + 'emplois/', {'q': 'comptab'}).json()['resultats'][0]['titre'], 'Comptable')

    def test_detail_et_postuler_une_fois(self):
        d = self.c.get(API + f'emplois/{self.b.pk}/').json()
        self.assertEqual(d['whatsapp'], '22890112233')
        self.assertFalse(d['deja_postule'])
        r = self.c.post(API + f'emplois/{self.b.pk}/postuler/', {'nom': 'Kofi', 'telephone': 'abc', 'message': 'x'})
        self.assertEqual(r.status_code, 400)
        cv = SimpleUploadedFile('cv.pdf', b'%PDF-1.4 cv', content_type='application/pdf')
        r = self.c.post(API + f'emplois/{self.b.pk}/postuler/', {'nom': 'Kofi', 'telephone': '+228 90 00 00 00', 'cv': cv},
                        format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        r = self.c.post(API + f'emplois/{self.b.pk}/postuler/', {'nom': 'Kofi', 'telephone': '90000000'})
        self.assertEqual(r.status_code, 400)
        mes = self.c.get(API + 'emplois/candidatures/').json()
        self.assertEqual(mes[0]['statut_libelle'], 'Reçue')
        self.assertNotIn('cv', str(self.c.get(API + f'emplois/{self.b.pk}/').json()))

    def test_cv_reserve_a_l_equipe_et_site(self):
        c = CandidatureEmploi.objects.create(offre=self.a, user=self.u, nom='K', telephone='90000000',
                                             cv=SimpleUploadedFile('cv.pdf', b'%PDF', content_type='application/pdf'))
        self.client.force_login(self.u)
        self.assertEqual(self.client.get(f'/emplois/cv/{c.pk}/').status_code, 404)
        admin = get_user_model().objects.create_superuser(email='ad@example.com', password='x-Pass-12345')
        self.client.force_login(admin)
        r = self.client.get(f'/emplois/cv/{c.pk}/')
        self.assertEqual(r.status_code, 200)
        r.close()
        self.assertContains(self.client.get('/emplois/'), 'Développeur web')
        self.assertContains(self.client.get(f'/emplois/{self.b.pk}/'), 'wa.me/22890112233')
        self.assertEqual(self.client.get(f'/lantanteAdminTech/Offres/offreemploi/').status_code, 200)
