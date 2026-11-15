"""Paiement direct Mobile Money en panne chez l'opérateur : bascule sur la page FedaPay de la même transaction."""
from unittest import mock

from django.test import TestCase, override_settings

from . import fedapay
from .models import Payment


class Rep:
    def __init__(self, code, data):
        self.status_code, self._d = code, data

    def json(self):
        return self._d


def faux(code_direct):
    def req(method, url, json=None, headers=None, timeout=None):
        if url.endswith('/transactions'):
            return Rep(200, {'v1/transaction': {'id': 42}})
        if url.endswith('/token'):
            return Rep(200, {'token': 'tk', 'url': 'https://process.fedapay.com/tk'})
        return Rep(code_direct, {})
    return req


@override_settings(FEDAPAY_SECRET_KEY='sk_live_x', FEDAPAY_ENVIRONMENT='live')
class SecoursTests(TestCase):
    def _p(self):
        return Payment.objects.create(kind='soutien', amount=500, description='Soutien', first_name='Ama',
                                      last_name='Koffi', phone='+22892000000', operator='togocel', mode='live')

    def test_erreur_500_de_l_operateur_page_fedapay(self):
        p = self._p()
        with mock.patch('Payments.fedapay.requests.request', side_effect=faux(500)), \
                mock.patch('Payments.fedapay.secret_key', return_value='sk'):
            url = fedapay.start(p, 'https://x/cb')
        p.refresh_from_db()
        self.assertEqual((url, p.status, p.payment_url, p.fedapay_id), ('https://process.fedapay.com/tk', 'pending',
                                                                           'https://process.fedapay.com/tk', '42'))

    def test_numero_refuse_reste_une_erreur(self):
        p = self._p()
        with mock.patch('Payments.fedapay.requests.request', side_effect=faux(400)), \
                mock.patch('Payments.fedapay.secret_key', return_value='sk'), \
                self.assertRaises(fedapay.FedaPayError):
            fedapay.start(p, 'https://x/cb')

    def test_envoi_direct_ok(self):
        p = self._p()
        with mock.patch('Payments.fedapay.requests.request', side_effect=faux(200)), \
                mock.patch('Payments.fedapay.secret_key', return_value='sk'):
            self.assertIsNone(fedapay.start(p, 'https://x/cb'))
