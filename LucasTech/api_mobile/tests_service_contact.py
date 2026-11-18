from django.contrib.auth import get_user_model
from django.test import TestCase

from Services.models import Service


class ServiceContactTests(TestCase):
    def test_detail_et_clics(self):
        u = get_user_model().objects.create_user(email='s@x.tg', password='x')
        s = Service.objects.create(admin=u, title='Site web', description='Création de site.')
        d = self.client.get(f'/api/mobile/v1/services/{s.pk}/').json()
        self.assertIn('lien', d)
        self.assertTrue(d['lien'].startswith('http'))
        for sorte in ('whatsapp', 'support', 'support'):
            self.assertEqual(self.client.post(f'/api/mobile/v1/services/{s.pk}/clic/{sorte}/').status_code, 200)
        self.assertEqual(self.client.post(f'/api/mobile/v1/services/{s.pk}/clic/autre/').status_code, 404)
        s.refresh_from_db()
        self.assertEqual((s.clics_whatsapp, s.clics_support), (1, 2))
