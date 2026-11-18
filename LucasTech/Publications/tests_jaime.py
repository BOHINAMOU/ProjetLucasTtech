"""« J'aime » des actualités : unique par compte, double clic, requêtes simultanées, site et appli."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import Publication, PublicationLike, basculer_like

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


@override_settings(STORAGES=STORAGES)
class JaimeTests(TestCase):
    def setUp(self):
        cache.clear()
        U = get_user_model()
        self.a = U.objects.create_user(email='a@x.tg', password='x')
        self.b = U.objects.create_user(email='b@x.tg', password='x')
        self.p = Publication.objects.create(title='Titre', slug='titre', content='x', is_published=True, author=self.a)

    def test_unicite_en_base(self):
        PublicationLike.objects.create(publication=self.p, user=self.a)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PublicationLike.objects.create(publication=self.p, user=self.a)

    def test_double_clic_retire_puis_remet(self):
        self.assertEqual(basculer_like(self.p, self.a), (True, 1))
        self.assertEqual(basculer_like(self.p, self.a), (False, 0))
        self.assertEqual(basculer_like(self.p, self.a), (True, 1))
        self.assertEqual(basculer_like(self.p, self.b), (True, 2))

    def test_requete_simultanee_ne_double_pas(self):
        # une autre requête du même compte vient d'enregistrer le « J'aime » entre notre lecture et notre insertion :
        # la base refuse le doublon, pas d'erreur, toujours un seul « J'aime »
        PublicationLike.objects.create(publication=self.p, user=self.a)
        with mock.patch('django.db.models.query.QuerySet.delete', return_value=(0, {})):
            self.assertEqual(basculer_like(self.p, self.a), (True, 1))
        self.assertEqual(PublicationLike.objects.filter(publication=self.p, user=self.a).count(), 1)

    def test_api_appli(self):
        c = APIClient()
        self.assertEqual(c.post(f'/api/mobile/v1/publications/{self.p.pk}/aimer/').status_code, 401)
        c.force_authenticate(self.a)
        r = c.post(f'/api/mobile/v1/publications/{self.p.pk}/aimer/').json()
        self.assertEqual(r, {'aime': True, 'likes': 1})
        self.assertEqual(c.get('/api/mobile/v1/publications/aimes/').json(), [self.p.pk])
        liste = c.get('/api/mobile/v1/publications/').json()
        liste = liste['resultats'] if isinstance(liste, dict) else liste
        self.assertEqual(liste[0]['likes'], 1)
        self.assertEqual(c.get(f'/api/mobile/v1/publications/{self.p.pk}/').json()['likes'], 1)
        self.assertEqual(c.post(f'/api/mobile/v1/publications/{self.p.pk}/aimer/').json(), {'aime': False, 'likes': 0})

    def test_site(self):
        url = '/actualites/titre/aimer/'
        r = self.client.post(url)
        self.assertEqual(r.status_code, 401)
        self.assertIn('connexion', r.json()['connexion'])
        self.client.force_login(self.b)
        self.assertEqual(self.client.post(url).json(), {'aime': True, 'likes': 1})
        page = self.client.get('/actualites/titre/')
        self.assertContains(page, 'id="nd-like"')
        self.assertContains(page, 'nd-like on')
