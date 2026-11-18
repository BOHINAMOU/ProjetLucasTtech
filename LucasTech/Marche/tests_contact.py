from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings

from Marche.models import ContactVendeur

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402

PNG = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) + b'0' * 64
OK = {'nom': 'Kossi', 'prenom': 'Ama', 'boutique': 'Mode Ama', 'telephone': '90 12 34 56', 'email': 'ama@x.tg', 'ville': 'Lomé',
      'message': '', 'piece_type': 'cni', 'accord': '1'}


def envoi(**k):
    d = dict(OK, piece=SimpleUploadedFile('ma-carte.png', PNG, content_type='image/png'))
    d.update(k)
    return d


@override_settings(STORAGES=STORAGES)
class ContactVendeurTests(TestCase):
    def setUp(self):
        cache.clear()
        get_user_model().objects.create_superuser(email='admin@x.tg', password='x')

    def test_page_whatsapp_et_formulaire(self):
        r = self.client.get('/vendre/')
        self.assertContains(r, 'Envoyer ma demande')
        if 'class="vc-wa"' in r.content.decode():
            self.assertContains(r, 'je%20veux%20vendre%20sur%20Lantante')

    def test_envoi_enregistre_et_previent(self):
        r = self.client.post('/vendre/', envoi())
        self.assertRedirects(r, '/vendre/?envoye=1#formulaire', fetch_redirect_response=False)
        c = ContactVendeur.objects.get()
        self.assertEqual((c.telephone, c.statut), ('22890123456', 'nouvelle'))
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ['admin@x.tg', 'ama@x.tg'])
        self.assertTrue(c.consentement and c.piece)
        self.assertNotIn('ma-carte', c.piece.name)  # nom aléatoire
        self.assertFalse(any(m.attachments for m in mail.outbox))  # jamais en pièce jointe
        self.assertEqual(self.client.get(f'/vendre/piece-contact/{c.pk}/').status_code, 302)  # pas connecté → connexion
        self.assertContains(self.client.get('/vendre/?envoye=1'), 'Demande envoyée, nous vous contactons vite.')

    def test_validation_et_anti_spam(self):
        r = self.client.post('/vendre/', envoi(telephone='12', email='x'))
        self.assertContains(r, 'Numéro invalide')
        self.assertContains(r, 'E-mail invalide')
        self.client.post('/vendre/', envoi(site_internet='spam'))
        r = self.client.post('/vendre/', envoi(piece=SimpleUploadedFile('faux.png', b'MZ' + b'0' * 64)))
        self.assertContains(r, 'Format accepté')
        r = self.client.post('/vendre/', envoi(accord=''))
        self.assertContains(r, 'Cochez la case')
        self.assertEqual(ContactVendeur.objects.count(), 0)
        for _ in range(6):
            self.client.post('/vendre/', envoi())
        self.assertEqual(ContactVendeur.objects.count(), 5)

    def test_admin_creer_le_vendeur_depuis_la_demande(self):
        self.client.post('/vendre/', envoi())
        c = ContactVendeur.objects.get()
        self.client.login(email='admin@x.tg', password='x')
        r = self.client.get(f'/lantanteAdminTech/Marche/contactvendeur/{c.pk}/change/')
        self.assertContains(r, 'Créer le vendeur')
        self.assertContains(r, f'/vendre/piece-contact/{c.pk}/')
        self.assertEqual(self.client.get(f'/vendre/piece-contact/{c.pk}/').status_code, 200)
        url = f'/lantanteAdminTech/Marche/vendeur/add/?boutique=Mode+Ama&email=ama%40x.tg&whatsapp=22890123456&ville=Lom%C3%A9&contact={c.pk}'
        self.assertContains(self.client.get(url), 'ama@x.tg')
        r = self.client.post(url, {'boutique': 'Mode Ama', 'email': 'ama@x.tg', 'whatsapp': '22890123456', 'ville': 'Lomé',
                                   'commission_pct': '10', 'duree': '3'})
        self.assertEqual(r.status_code, 302)
        c.refresh_from_db()
        self.assertEqual(c.statut, 'compte_cree')
        self.assertIsNotNone(c.vendeur and c.vendeur.fin_acces)
