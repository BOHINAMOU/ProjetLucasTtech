import re
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from Payments.models import Payment

from .models import Formation

GIF = (b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,'
       b'\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;')
TMP = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TMP, PRIVATE_MEDIA_ROOT=TMP, DEBUG=True, FEDAPAY_SECRET_KEY='')
class AchatPdfSansCompteTests(TestCase):
    """Un visiteur sans compte paie un PDF : le téléchargement est proposé tout de suite, sans connexion."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        auteur = get_user_model().objects.create_user(email='auteur@exemple.tg', password='x-Secret-123')
        self.f = Formation.objects.create(
            author=auteur, formation_type='numerique', title='Formation TikTok France',
            description='Guide', price=2100,
            image=SimpleUploadedFile('c.gif', GIF, content_type='image/gif'))
        self.f.file.save('Formation_TikTok_France.pdf', ContentFile(b'%PDF-1.4 test'))

    def test_paiement_puis_telechargement(self):
        page = self.client.get(f'/formations/{self.f.pk}/')
        self.assertContains(page, f'/paiement/formation/{self.f.pk}/')

        r = self.client.post(f'/paiement/formation/{self.f.pk}/', {
            'first_name': 'Ama', 'last_name': 'Koffi', 'whatsapp': '90000000', 'city': 'Lomé',
            'country': 'tg', 'operator': 'togocel', 'phone': '90000000', 'account': 'guest'})
        self.assertEqual(r.status_code, 302, r.context and r.context['form'].errors)
        p = Payment.objects.get()
        self.assertEqual(int(p.amount), 2100)
        self.assertIsNone(p.user)

        # Avant paiement : pas de fichier
        self.assertEqual(self.client.get(f'/paiement/recu/{p.reference}/fichier/').status_code, 404)

        self.client.post(f'/paiement/demo/{p.reference}/', {'action': 'pay'})
        p.refresh_from_db()
        self.assertTrue(p.is_paid)

        res = self.client.get(f'/paiement/recu/{p.reference}/')
        self.assertContains(res, 'Télécharger le PDF')
        self.assertTrue(res.context['auto_file'])  # téléchargement lancé automatiquement

        dl = self.client.get(f'/paiement/recu/{p.reference}/fichier/')
        self.assertEqual(dl.status_code, 200)
        self.assertIn('attachment', dl['Content-Disposition'])
        self.assertEqual(b''.join(dl.streaming_content), b'%PDF-1.4 test')

        # Le lien avec jeton marche aussi sur un autre appareil, sans compte
        autre = self.client_class()
        url = re.sub(r'^https?://[^/]+', '', p.get_absolute_url())
        self.assertEqual(autre.get(url).status_code, 200)
        self.assertEqual(autre.get(f'/paiement/recu/{p.reference}/fichier/?t={p.access_token}').status_code, 200)
        # Sans jeton : refusé
        self.assertEqual(self.client_class().get(f'/paiement/recu/{p.reference}/fichier/').status_code, 404)
