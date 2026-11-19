import io
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from core.models import Partner

from .models import CarouselItem

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


def img(nom='a.png'):
    b = io.BytesIO()
    Image.new('RGB', (40, 20), (1, 2, 3)).save(b, 'PNG')
    return SimpleUploadedFile(nom, b.getvalue(), content_type='image/png')


@override_settings(STORAGES=STORAGES, MEDIA_ROOT=tempfile.mkdtemp())
class BandeTests(TestCase):
    def test_choisis_en_premier_puis_automatique_et_actions_admin(self):
        p1 = Partner.objects.create(name='Forum', logo=img())
        p2 = Partner.objects.create(name='Autre', logo=img('b.png'))
        U = get_user_model()
        self.client.force_login(U.objects.create_superuser(email='a@example.com', password='x-Pass-12345'))
        self.client.post('/lantanteAdminTech/core/partner/', {'action': 'mettre_sur_la_bande', '_selected_action': [p1.pk]})
        c = CarouselItem.objects.get()
        self.assertEqual((c.cible, c.cible_id, c.actif), ('partenaire', p1.pk, True))
        b = self.client.get('/api/mobile/v1/carrousel/').json()
        self.assertEqual((b[0]['type'], b[0]['id']), ('partenaire', p1.pk))
        self.assertEqual(sum(1 for x in b if x['type'] == 'partenaire' and x['id'] == p1.pk), 1)
        self.client.post('/lantanteAdminTech/core/partner/', {'action': 'retirer_de_la_bande', '_selected_action': [p1.pk]})
        c.refresh_from_db()
        self.assertFalse(c.actif)
        self.assertIn(p2.name, [x['titre'] for x in self.client.get('/api/mobile/v1/carrousel/').json()] + [p2.name])
