"""Administration : tableau de bord (argent), paiements (suppression protégée, export), événements, formations."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

A = '/lantanteAdminTech/'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


@override_settings(STORAGES=STORAGES)
class AdminTests(TestCase):
    def setUp(self):
        from Events.models import Event
        from Payments.models import Payment
        self.admin = get_user_model().objects.create_superuser(email='admin@example.com', password='x-Pass-12345')
        self.client.force_login(self.admin)
        self.e = Event.objects.create(title='Un sourire', description='x', location='Lomé', kind='soutien',
                                      starts_at=timezone.now() + timedelta(days=1))
        base = dict(kind='soutien', event=self.e, first_name='Ama', last_name='Koffi', phone='+22890000000',
                    description='Soutien : Un sourire')
        self.paye = Payment.objects.create(status='approved', amount=2000, paid_at=timezone.now(), **base)
        self.attente = Payment.objects.create(status='pending', amount=500, **base)

    def test_tableau_de_bord(self):
        r = self.client.get(A + '')
        self.assertContains(r, 'Argent encaissé')
        self.assertContains(r, '2\u202f000 F')
        self.assertContains(r, '10 derniers paiements')

    def test_liste_evenements_payeurs_et_total(self):
        r = self.client.get(A + 'Events/event/')
        self.assertContains(r, 'Un sourire')
        self.assertContains(r, '2\u202f000 F')
        r = self.client.get(A + f'Events/event/{self.e.pk}/change/')
        self.assertContains(r, 'Participants et donateurs')
        self.assertContains(r, 'Gérer les paiements')

    def test_paiements_resume_export_et_suppression_protegee(self):
        from Payments.models import Payment
        r = self.client.get(A + f'Payments/payment/?event__id__exact={self.e.pk}')
        self.assertContains(r, 'Encaissé (sélection)')
        r = self.client.post(A + 'Payments/payment/', {'action': 'exporter_csv',
                                                          '_selected_action': [self.paye.pk, self.attente.pk]})
        self.assertEqual(r['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('Ama', r.content.decode('utf-8'))
        # suppression : seule la ligne non payée part
        self.client.post(A + 'Payments/payment/', {'action': 'supprimer_non_payes', 'post': 'yes',
                                                      '_selected_action': [self.paye.pk, self.attente.pk]})
        self.assertTrue(Payment.objects.filter(pk=self.paye.pk).exists())
        self.assertFalse(Payment.objects.filter(pk=self.attente.pk).exists())
        # un paiement réussi ne se supprime pas, il se marque « Remboursé »
        self.assertEqual(self.client.get(A + f'Payments/payment/{self.paye.pk}/delete/').status_code, 403)
        self.client.post(A + 'Payments/payment/', {'action': 'marquer_rembourse', '_selected_action': [self.paye.pk]})
        self.paye.refresh_from_db()
        self.assertEqual(self.paye.status, 'refunded')

    def test_listes_formations_boutique_abonnements(self):
        for url in (A + 'Formations/formation/', A + 'Shop/shoporder/', A + 'abonnements/usersubscription/'):
            self.assertEqual(self.client.get(url).status_code, 200, url)
