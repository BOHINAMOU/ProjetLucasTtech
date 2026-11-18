from django.core import mail
from django.test import TestCase, override_settings

from core.emails import analyser, embellir


class EmailsTests(TestCase):
    def test_code_bouton_signature(self):
        b = analyser("Votre code", "Bonjour,\n\nVotre code : 482915\n\nOuvrir : https://x.tg/a/\n\nL'équipe Lantante")
        types = [t for t, _ in b]
        self.assertIn(('code', '482915'), b)
        self.assertIn(('bouton', ('Ouvrir', 'https://x.tg/a/')), b)
        self.assertEqual(types.count('p'), 2)  # Bonjour + « Votre code : » ; signature retirée

    def test_montant_pas_pris_pour_un_code(self):
        b = analyser("Code promo", "Votre commande de 100 000 CFA est prête.")
        self.assertNotIn('code', [t for t, _ in b])

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_version_html_ajoutee(self):
        m = embellir(mail.EmailMessage("Test", "Bonjour,\n\nCode : 123456", None, ['a@x.tg']))
        self.assertEqual(m.alternatives[0][1], 'text/html')
        self.assertIn('123456', m.alternatives[0][0])
        self.assertIn('banniere.jpg', m.alternatives[0][0])
        self.assertEqual(m.body, "Bonjour,\n\nCode : 123456")
