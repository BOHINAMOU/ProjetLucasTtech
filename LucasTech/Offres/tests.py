import datetime
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import OffreEmploi

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

    def test_detail_contacts_et_clics(self):
        d = self.c.get(API + f'emplois/{self.b.pk}/').json()
        self.assertEqual(d['whatsapp'], '22890112233')
        self.assertIn('Développeur web', d['message_whatsapp'])
        self.assertNotIn('postuler', d)
        APIClient().post(API + f'emplois/{self.b.pk}/clic/whatsapp/')
        APIClient().post(API + f'emplois/{self.b.pk}/clic/inconnu/')
        self.b.refresh_from_db()
        self.assertEqual((self.b.clics_whatsapp, self.b.vues), (1, 1))

    def test_au_moins_un_contact_et_site(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            OffreEmploi(titre='X', entreprise='Y', description='z').full_clean()
        self.assertContains(self.client.get('/emplois/'), 'Développeur web')
        self.assertContains(self.client.get(f'/emplois/{self.b.pk}/'), 'wa.me/22890112233')
        admin = get_user_model().objects.create_superuser(email='ad@example.com', password='x-Pass-12345')
        self.client.force_login(admin)
        self.assertEqual(self.client.get('/lantanteAdminTech/Offres/offreemploi/').status_code, 200)
