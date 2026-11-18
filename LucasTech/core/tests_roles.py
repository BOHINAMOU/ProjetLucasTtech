"""Rôles délégués : chacun ne voit que son périmètre et ses chiffres ; pages de section pour l'équipe."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
A = '/lantanteAdminTech/'


@override_settings(STORAGES=STORAGES)
class RolesTests(TestCase):
    def setUp(self):
        from Events.models import Event
        from Payments.models import Payment
        from Services.models import InscriptionService, Service
        from core.models import Delegation
        U = get_user_model()
        self.boss = U.objects.create_superuser(email='boss@example.com', password='x-Pass-12345')
        self.d = U.objects.create_user(email='d@example.com', password='x-Pass-12345', is_verified=True, first_name='Kossi')
        self.e1 = Event.objects.create(title='Gala des orphelins', description='x', kind='soutien')
        self.e2 = Event.objects.create(title='Concert secret', description='x')
        base = dict(first_name='Ama', last_name='Koffi', phone='+22890000000', status='approved')
        Payment.objects.create(kind='soutien', event=self.e1, amount=2000, description='Soutien gala', **base)
        Payment.objects.create(kind='ticket', event=self.e2, amount=9000, description='Ticket concert', **base)
        self.s1 = Service.objects.create(admin=self.boss, title='Création de compte', description='x')
        self.s2 = Service.objects.create(admin=self.boss, title='Service caché', description='x')
        InscriptionService.objects.create(service=self.s1, reponses={'Nom': 'Ama'})
        InscriptionService.objects.create(service=self.s2, reponses={'Nom': 'Invisible'})
        Delegation.objects.create(user=self.d, type='evenement', event=self.e1)
        Delegation.objects.create(user=self.d, type='service', service=self.s1)
        self.d.refresh_from_db()

    def test_delegue_ne_voit_que_son_perimetre(self):
        self.assertTrue(self.d.is_staff)
        self.client.force_login(self.d)
        r = self.client.get(A)
        self.assertContains(r, 'Gala des orphelins')
        self.assertContains(r, '2\u202f000 CFA')
        self.assertNotContains(r, 'Concert secret')
        self.assertNotContains(r, 'Encaissé · 30 jours')  # pas les chiffres globaux
        r = self.client.get(A + 'Events/event/')
        self.assertContains(r, 'Gala des orphelins')
        self.assertNotContains(r, 'Concert secret')
        r = self.client.get(A + 'Payments/payment/')
        self.assertContains(r, 'Soutien gala')
        self.assertNotContains(r, 'Ticket concert')
        r = self.client.get(A + 'Services/inscriptionservice/')
        self.assertContains(r, 'Ama')
        self.assertNotContains(r, 'Invisible')
        self.assertEqual(self.client.get(f'{A}Events/event/{self.e2.pk}/change/').status_code, 302)
        self.assertEqual(self.client.get(A + 'section/paiements/').status_code, 404)

    def test_pages_de_section_pour_l_equipe(self):
        self.client.force_login(self.boss)
        for code in ('paiements', 'evenements', 'services', 'ecoles', 'publications', 'concours', 'utilisateurs'):
            r = self.client.get(f'{A}section/{code}/')
            self.assertEqual(r.status_code, 200, code)
        self.assertContains(self.client.get(A + 'section/evenements/'), '11\u202f000 CFA')
        self.assertContains(self.client.get(A), 'Encaissé · 30 jours')
