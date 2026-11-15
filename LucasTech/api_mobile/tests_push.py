"""Notifications push FCM : enregistrement des téléphones, envoi, jetons périmés, absence de clé."""
import json
import os
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from rest_framework.test import APITestCase

from . import push
from .models import Appareil, Notification

API = '/api/mobile/v1/'
J1, J2 = 'a' * 40, 'b' * 40


class Rep:
    def __init__(self, code, text=''):
        self.status_code, self.text = code, text


class PushTests(APITestCase):
    def setUp(self):
        U = get_user_model()
        self.u = U.objects.create_user(email='p@example.com', password='x-Pass-12345', is_verified=True)
        self.v = U.objects.create_user(email='q@example.com', password='x-Pass-12345', is_verified=True)
        self.client.force_authenticate(self.u)
        f = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        json.dump({'project_id': 'demo', 'client_email': 'x@demo.iam', 'token_uri': 'https://oauth2.example/token',
                   'private_key': 'k'}, f)
        f.close()
        self.cle = f.name
        self.addCleanup(os.unlink, f.name)

    def test_enregistrement_et_oubli(self):
        self.assertEqual(self.client.post(API + 'appareils/', {'jeton': 'court'}, format='json').status_code, 400)
        self.client.post(API + 'appareils/', {'jeton': J1, 'plateforme': 'android'}, format='json')
        self.client.post(API + 'appareils/', {'jeton': J1, 'plateforme': 'android'}, format='json')  # rafraîchi
        self.assertEqual(Appareil.objects.filter(user=self.u).count(), 1)
        # le même téléphone passe sur un autre compte
        self.client.force_authenticate(self.v)
        self.client.post(API + 'appareils/', {'jeton': J1}, format='json')
        self.assertEqual(Appareil.objects.get(jeton=J1).user, self.v)
        self.client.post(API + 'appareils/oublier/', {'jeton': J1}, format='json')
        self.assertFalse(Appareil.objects.exists())
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(API + 'appareils/', {'jeton': J2}, format='json').status_code, 401)

    def test_sans_cle_rien_ne_part_et_rien_ne_casse(self):
        Appareil.objects.create(user=self.u, jeton=J1)
        with override_settings(FIREBASE_SA_PATH=''), mock.patch('api_mobile.push.requests.post') as post:
            n = Notification.objects.create(titre='T', message='M', audience='personne', utilisateur=self.u)
            self.assertEqual(push.envoyer(n), 0)
        post.assert_not_called()

    def test_envoi_cible_et_jeton_perime(self):
        Appareil.objects.create(user=self.u, jeton=J1)
        Appareil.objects.create(user=self.v, jeton=J2)
        envoyes = []

        def faux_post(url, json=None, headers=None, timeout=None, data=None):
            envoyes.append(json['message']['token'])
            return Rep(404, '{"error":{"status":"NOT_FOUND","details":[{"errorCode":"UNREGISTERED"}]}}') \
                if json['message']['token'] == J2 else Rep(200)

        with override_settings(FIREBASE_SA_PATH=self.cle), \
                mock.patch('api_mobile.push._access_token', return_value='tok'), \
                mock.patch('api_mobile.push.requests.post', side_effect=faux_post):
            n = Notification.objects.create(titre='Paiement reçu', message='Merci', audience='personne',
                                            utilisateur=self.u, cible='concours', cible_id=3)
            self.assertEqual(push.envoyer(n), 1)
            self.assertEqual(envoyes, [J1])  # seulement le destinataire
            envoyes.clear()
            tous = Notification.objects.create(titre='Info', message='Pour tous', audience='tous')
            self.assertEqual(push.envoyer(tous), 1)
            self.assertCountEqual(envoyes, [J1, J2])
        self.assertFalse(Appareil.objects.filter(jeton=J2).exists())  # jeton périmé supprimé

    def test_groupe(self):
        g = Group.objects.create(name='Élèves')
        self.v.groups.add(g)
        Appareil.objects.create(user=self.u, jeton=J1)
        Appareil.objects.create(user=self.v, jeton=J2)
        n = Notification.objects.create(titre='G', message='M', audience='groupe', groupe=g)
        self.assertEqual(list(push.destinataires(n).values_list('jeton', flat=True)), [J2])

    def test_creation_declenche_envoi_apres_commit(self):
        with override_settings(FIREBASE_SA_PATH=self.cle), mock.patch('api_mobile.push.envoyer') as env,                 mock.patch('api_mobile.push.threading.Thread') as th:
            with self.captureOnCommitCallbacks(execute=True):
                Notification.objects.create(titre='T', message='M', audience='tous')
            th.assert_called_once()
            th.call_args.kwargs['target']()
            env.assert_called_once()
