import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.test import TestCase, override_settings

from Publications.models import Publication, PublicationComment
from .dashboard import SECTIONS

TMP = tempfile.mkdtemp()


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
                   MEDIA_ROOT=TMP, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RubriquesTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.admin = U.objects.create_superuser(email='a@x.tg', password='x')
        self.client.force_login(self.admin)

    def test_toutes_les_rubriques_s_affichent(self):
        for code in SECTIONS:
            r = self.client.get(f'/lantanteAdminTech/section/{code}/')
            self.assertEqual(r.status_code, 200, code)
        r = self.client.get('/lantanteAdminTech/section/emplois/')
        self.assertContains(r, 'Offres en ligne')
        r = self.client.get('/lantanteAdminTech/section/boutique/')
        self.assertContains(r, 'Codes promo')

    def test_delegue_voit_seulement_ses_rubriques(self):
        U = get_user_model()
        d = U.objects.create_user(email='d@x.tg', password='x', is_staff=True)
        d.user_permissions.add(Permission.objects.get(codename='view_offreemploi'))
        self.client.force_login(d)
        self.assertEqual(self.client.get('/lantanteAdminTech/section/emplois/').status_code, 200)
        self.assertEqual(self.client.get('/lantanteAdminTech/section/paiements/').status_code, 404)

    def test_reponse_envoyee_par_email(self):
        p = Publication.objects.create(title='Titre', slug='titre', content='x', is_published=True, author=self.admin)
        c = PublicationComment.objects.create(publication=p, name='Ama', text='Bravo', email='ama@x.tg', is_hidden=True)
        url = f'/lantanteAdminTech/Publications/publicationcomment/{c.pk}/change/'
        r = self.client.post(url, {'is_hidden': 'on', 'is_read': 'on', 'reponse': 'Merci Ama'})
        self.assertEqual(r.status_code, 302)
        c.refresh_from_db()
        self.assertIsNotNone(c.repondu_le)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Merci Ama', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ['ama@x.tg'])
