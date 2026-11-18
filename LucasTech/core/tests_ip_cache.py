from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from core.ip import ip_client

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


class IpTests(TestCase):
    def test_adresse_falsifiee_ignoree(self):
        rf = RequestFactory()
        # le client envoie une fausse adresse ; nginx ajoute la vraie à la fin et la met dans X-Real-IP
        r = rf.get('/', HTTP_X_FORWARDED_FOR='1.2.3.4, 41.207.10.5', HTTP_X_REAL_IP='41.207.10.5', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(ip_client(r), '41.207.10.5')
        r = rf.get('/', HTTP_X_FORWARDED_FOR='1.2.3.4, 41.207.10.5', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(ip_client(r), '41.207.10.5')
        self.assertEqual(ip_client(rf.get('/', REMOTE_ADDR='10.0.0.9')), '10.0.0.9')

    def test_limite_api_non_contournable(self):
        from rest_framework.settings import api_settings
        from rest_framework.throttling import AnonRateThrottle
        self.assertEqual(api_settings.NUM_PROXIES, 1)
        rf = RequestFactory()
        t = AnonRateThrottle()
        a = rf.get('/', HTTP_X_FORWARDED_FOR='9.9.9.1, 41.207.10.5', REMOTE_ADDR='127.0.0.1')
        b = rf.get('/', HTTP_X_FORWARDED_FOR='9.9.9.2, 41.207.10.5', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(t.get_ident(a), t.get_ident(b))  # changer l'adresse falsifiée ne change rien


@override_settings(STORAGES=STORAGES)
class CacheListesTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_cache_puis_vide_a_la_modification(self):
        from Hotels.models import Hotel
        Hotel.objects.create(nom='Hôtel A', ville='Lomé')
        r1 = self.client.get('/api/mobile/v1/hotels/')
        r2 = self.client.get('/api/mobile/v1/hotels/')
        self.assertEqual(r2['X-Cache'], 'HIT')
        self.assertEqual(r1.json(), r2.json())
        Hotel.objects.create(nom='Hôtel B', ville='Kara')  # modification dans l'admin : cache vidé
        r3 = self.client.get('/api/mobile/v1/hotels/')
        self.assertFalse(r3.has_header('X-Cache'))
        self.assertEqual(len(r3.json()['resultats']), 2)

    def test_pas_de_cache_pour_un_compte_connecte_sur_les_listes_personnelles(self):
        from django.contrib.auth import get_user_model
        from rest_framework.authtoken.models import Token
        u = get_user_model().objects.create_user(email='c@x.tg', password='x')
        tok = Token.objects.create(user=u)
        self.client.get('/api/mobile/v1/emplois/')
        r = self.client.get('/api/mobile/v1/emplois/', HTTP_AUTHORIZATION=f'Token {tok.key}')
        self.assertFalse(r.has_header('X-Cache'))
        self.assertEqual(self.client.get('/api/mobile/v1/emplois/')['X-Cache'], 'HIT')
