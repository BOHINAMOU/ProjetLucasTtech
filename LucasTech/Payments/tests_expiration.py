from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from . import services
from .models import Payment


class ExpirationTests(TestCase):
    def setUp(self):
        cache.clear()

    def _p(self, minutes, **k):
        p = Payment.objects.create(kind='soutien', amount=500, description='Soutien', first_name='Ama', last_name='Koffi',
                                   phone='+22892000000', operator='togocel', mode='live', fedapay_id=k.pop('fid', '77'), **k)
        Payment.objects.filter(pk=p.pk).update(created_at=timezone.now() - timedelta(minutes=minutes))
        p.refresh_from_db()
        return p

    def _statut(self, p):
        p.refresh_from_db()
        return p.status

    def test_attente_trop_longue_passe_en_annule_apres_verification(self):
        vieux, recent = self._p(45), self._p(5, fid='78')
        with mock.patch('Payments.fedapay.transaction_status', return_value='pending'):
            self.assertEqual(services.expirer_anciens(), 1)
        self.assertEqual((self._statut(vieux), self._statut(recent)), ('canceled', 'pending'))
        vieux.refresh_from_db()
        self.assertEqual(vieux.failure_reason, services.EXPIRE)

    def test_paye_chez_l_operateur_est_livre_pas_annule(self):
        p = self._p(45)
        with mock.patch('Payments.fedapay.transaction_status', return_value='approved'), \
                mock.patch('Payments.services._fulfill'):
            services.expirer_anciens()
        self.assertEqual(self._statut(p), 'approved')

    def test_operateur_injoignable_on_ne_touche_a_rien(self):
        p = self._p(45)
        with mock.patch('Payments.fedapay.transaction_status', return_value=''):
            self.assertEqual(services.expirer_anciens(), 0)
        self.assertEqual(self._statut(p), 'pending')

    def test_validation_tardive_apres_expiration_est_livree(self):
        p = self._p(45)
        with mock.patch('Payments.fedapay.transaction_status', return_value='pending'):
            services.expirer_anciens()
        with mock.patch('Payments.fedapay.transaction_status', return_value='approved'), \
                mock.patch('Payments.services._fulfill'):
            from django.urls import reverse
            r = self.client.post(reverse('payments:webhook'), '{"entity": {"id": 77}}', content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._statut(p), 'approved')

    def test_au_plus_une_fois_toutes_les_5_minutes(self):
        self._p(45)
        with mock.patch('Payments.fedapay.transaction_status', return_value='pending'):
            self.assertEqual(services.expirer_si_besoin(), 1)
            self._p(50, fid='79')
            self.assertEqual(services.expirer_si_besoin(), 0)
