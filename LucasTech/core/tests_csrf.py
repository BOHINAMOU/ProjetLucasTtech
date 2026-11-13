"""Connexion sur téléphone : jetons CSRF frais et échec CSRF convivial (au lieu de la page jaune 403)."""
import re

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}

LOGIN = '/users/connexion/'


def token(html):
    return re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)


@override_settings(STORAGES=STORAGES)
class CsrfLoginTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(email='eleve@example.com', password='x-Pass-12345', is_verified=True)
        self.c = Client(enforce_csrf_checks=True)

    def _login(self, tok, password='x-Pass-12345', referer=None):
        extra = {'HTTP_REFERER': referer} if referer else {}
        return self.c.post(LOGIN, {'csrfmiddlewaretoken': tok, 'username': 'eleve@example.com',
                                   'password': password}, **extra)

    def test_page_connexion_jamais_en_cache_et_cookie_pose(self):
        r = self.c.get(LOGIN)
        self.assertIn('no-store', r['Cache-Control'])
        self.assertIn('csrftoken', r.cookies)
        for url in ('/users/inscription/', '/users/mot-de-passe/oublie/'):
            r = self.c.get(url)
            self.assertIn('no-store', r['Cache-Control'], url)
            self.assertIn('csrftoken', r.cookies, url)

    def test_connexion_deconnexion_puis_reconnexion_avec_jeton_frais(self):
        r = self._login(token(self.c.get(LOGIN).content.decode()))
        self.assertEqual(r.status_code, 302)
        self.assertIn('_auth_user_id', self.c.session)
        profil = self.c.get('/users/profil/')
        self.assertIn('no-store', profil['Cache-Control'])
        r = self.c.post('/users/deconnexion/', {'csrfmiddlewaretoken': token(profil.content.decode())})
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('_auth_user_id', self.c.session)
        r = self._login(token(self.c.get(LOGIN).content.decode()))
        self.assertEqual(r.status_code, 302)
        self.assertIn('_auth_user_id', self.c.session)

    def test_jeton_perime_redirige_avec_message_au_lieu_du_403(self):
        old = token(self.c.get(LOGIN).content.decode())
        self.assertEqual(self._login(old).status_code, 302)   # la connexion renouvelle le jeton
        self.c.post('/users/deconnexion/', {'csrfmiddlewaretoken': token(self.c.get('/users/profil/').content.decode())})
        # page de connexion revenue par « Précédent » : ancien jeton
        r = self._login(old, referer='http://testserver/users/connexion/?next=/concours/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], 'http://testserver/users/connexion/?next=%2Fconcours%2F&session=expiree')
        page = self.c.get(r['Location'])
        self.assertContains(page, 'Votre session a expiré, veuillez réessayer.')
        self.assertNotIn('_auth_user_id', self.c.session)

    def test_echec_csrf_sans_referer_ou_externe_renvoie_a_la_connexion(self):
        r = self.c.post('/users/inscription/', {})
        self.assertEqual(r['Location'], '/users/connexion/?session=expiree')
        r = self.c.post('/users/inscription/', {}, HTTP_REFERER='https://evil.example/x')
        self.assertEqual(r['Location'], '/users/connexion/?session=expiree')


@override_settings(STORAGES=STORAGES)
class ApplicationPageTests(TestCase):
    def test_page_application(self):
        r = self.client.get('/application/')
        self.assertContains(r, 'href="/application/telecharger/')
        self.assertContains(r, 'iPhone : bientôt disponible')
        self.assertContains(self.client.get('/'), 'href="/application/"')

    def test_type_apk(self):
        import mimetypes
        self.assertEqual(mimetypes.guess_type('Lantante.apk')[0], 'application/vnd.android.package-archive')


@override_settings(STORAGES=STORAGES, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmailVerificationWebTests(TestCase):
    def test_inscription_web_code_obligatoire(self):
        from django.core import mail
        c = Client()
        r = c.post('/users/inscription/', {'email': 'nouveau@example.com', 'phone': '+22890000000', 'country': '',
                                           'city': '', 'password1': 'Un-Mot2Passe-solide',
                                           'password2': 'Un-Mot2Passe-solide'})
        self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and r.context['form'].errors)
        self.assertTrue(r['Location'].startswith('/users/verifier-email/'))
        self.assertNotIn('_auth_user_id', c.session)
        code = re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)
        # connexion refusée tant que l'e-mail n'est pas vérifié : renvoi vers la saisie du code
        c2 = Client()
        r = c2.post(LOGIN, {'username': 'nouveau@example.com', 'password': 'Un-Mot2Passe-solide'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].startswith('/users/verifier-email/'))
        self.assertNotIn('_auth_user_id', c2.session)
        code = re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)
        self.assertContains(c.get('/users/verifier-email/'), 'Vérifiez votre e-mail')
        r = c.post('/users/verifier-email/', {'action': 'verifier', 'code': code})
        self.assertEqual(r.status_code, 302)
        self.assertIn('_auth_user_id', c.session)
        self.assertTrue(get_user_model().objects.get(email='nouveau@example.com').is_verified)

    def test_comptes_staff_non_bloques(self):
        u = get_user_model().objects.create_user(email='staff@example.com', password='x-Pass-12345', is_staff=True)
        from Users.verification import is_verified
        self.assertTrue(is_verified(u))
