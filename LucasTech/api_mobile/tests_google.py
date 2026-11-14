"""« Continuer avec Google » dans l'appli (jeton Google simulé)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

API = '/api/mobile/v1/'
WEB = 'client-web.apps.googleusercontent.com'


def _info(**kw):
    d = {'aud': WEB, 'iss': 'https://accounts.google.com', 'sub': '1234567890', 'email': 'ama@gmail.com',
         'email_verified': 'true', 'given_name': 'Ama', 'family_name': 'Koffi', 'exp': '9999999999'}
    d.update(kw)
    return d


def _google(info, status=200):
    r = mock.Mock(status_code=status)
    r.json.return_value = info
    return mock.patch('requests.get', return_value=r)


@override_settings(SOCIAL_AUTH_GOOGLE_OAUTH2_KEY=WEB)
class GoogleTests(APITestCase):
    def test_nouveau_compte_verifie(self):
        with _google(_info()):
            r = self.client.post(API + 'auth/google/', {'id_token': 'x'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        u = get_user_model().objects.get(email='ama@gmail.com')
        self.assertTrue(u.is_verified)
        self.assertFalse(u.has_usable_password())
        self.assertTrue(r.json()['token'])
        self.assertEqual(self.client.get(API + 'me/', HTTP_AUTHORIZATION='Token ' + r.json()['token']).status_code, 200)

    def test_compte_existant_lie_par_email(self):
        u = get_user_model().objects.create_user(email='Ama@Gmail.com', password='x-Pass-12345', is_verified=False)
        with _google(_info()):
            r = self.client.post(API + 'auth/google/', {'id_token': 'x'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(get_user_model().objects.filter(email__iexact='ama@gmail.com').count(), 1)
        u.refresh_from_db()
        self.assertTrue(u.is_verified)
        from social_django.models import UserSocialAuth
        self.assertTrue(UserSocialAuth.objects.filter(user=u, provider='google-oauth2', uid='1234567890').exists())

    def test_jetons_refuses(self):
        for info, status in ((_info(aud='autre-appli'), 200), (_info(email_verified='false'), 200),
                             (_info(iss='https://pirate.example'), 200), (_info(exp='1'), 200), ({}, 400)):
            with _google(info, status):
                r = self.client.post(API + 'auth/google/', {'id_token': 'x'}, format='json')
            self.assertEqual(r.status_code, 400, info)
        self.assertFalse(get_user_model().objects.filter(email='ama@gmail.com').exists())

    def test_compte_suspendu(self):
        get_user_model().objects.create_user(email='ama@gmail.com', password='x-Pass-12345', is_active=False,
                                             is_verified=True)
        with _google(_info()):
            r = self.client.post(API + 'auth/google/', {'id_token': 'x'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_visiteur_voit_le_catalogue_mais_pas_l_historique(self):
        self.assertEqual(self.client.get(API + 'home/').status_code, 200)
        self.assertEqual(self.client.get(API + 'publications/').status_code, 200)
        self.assertEqual(self.client.get(API + 'concours/').status_code, 200)
        self.assertEqual(self.client.get(API + 'historique/').status_code, 401)
        self.assertEqual(self.client.post(API + 'paiements/', {}, format='json').status_code, 401)
