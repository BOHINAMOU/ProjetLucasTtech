"""Événements de soutien (dons) : API, paiement dans l'appli, historique, page du site."""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from Events.models import Event

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'


@override_settings(STORAGES=STORAGES)
class SoutienTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email='don@example.com', password='x-Pass-12345',
                                                         first_name='Ama', last_name='K', is_verified=True)
        self.e = Event.objects.create(title='Un sourire pour chaque orphelin', description='Aide.', location='Lomé',
                                      starts_at=timezone.now() + timedelta(days=1), kind='soutien', min_amount=100)

    def test_fiche_soutien(self):
        d = self.client.get(f'{API}evenements/{self.e.pk}/').json()
        self.assertEqual((d['type'], d['montant_min'], d['soutiens']), ('soutien', 100, 0))
        self.assertEqual(d['montants'], [500, 1000, 2000, 5000])

    @mock.patch('Payments.fedapay.is_enabled', return_value=True)
    @mock.patch('Payments.fedapay.mode', return_value='demo')
    def test_soutenir_dans_l_appli(self, *_):
        self.client.force_authenticate(self.user)
        r = self.client.post(API + 'paiements/', {'type': 'soutien', 'id': self.e.pk, 'montant': 50, 'pays': 'tg',
                                                  'operateur': 'togocel', 'telephone': '90000000'}, format='json')
        self.assertEqual(r.status_code, 400)  # sous le minimum
        r = self.client.post(API + 'paiements/', {'type': 'soutien', 'id': self.e.pk, 'montant': 1000, 'pays': 'tg',
                                                  'operateur': 'togocel', 'telephone': '90000000'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['montant'], 1000)
        h = self.client.get(API + 'historique/').json()
        self.assertEqual(h[0]['titre'], 'Soutien : Un sourire pour chaque orphelin')

    def test_visiteur_ne_peut_pas_payer(self):
        r = self.client.post(API + 'paiements/', {'type': 'soutien', 'id': self.e.pk, 'montant': 1000}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_page_du_site(self):
        r = self.client.get(self.e.get_absolute_url())
        self.assertContains(r, 'Soutenir cette cause')
        self.assertContains(r, 'Autre montant')
        self.assertNotContains(r, 'Aperçu')  # plus d'assistant en 3 étapes pour un don

    def test_evenement_du_jour_pas_termine(self):
        e = Event.objects.create(title='Ce matin', description='x', location='Lomé', kind='soutien',
                                 starts_at=max(timezone.now() - timedelta(minutes=5),
                                               timezone.localtime(timezone.now()).replace(hour=0, minute=1)))
        self.assertFalse(e.is_past)

    def test_liste_du_site_filtres(self):
        self.assertContains(self.client.get('/evenements/?type=soutien'), 'Un sourire pour chaque orphelin')
        self.assertNotContains(self.client.get('/evenements/?type=tickets'), 'Un sourire pour chaque orphelin')
        self.assertContains(self.client.get('/evenements/?q=sourire'), 'Un sourire pour chaque orphelin')

    def test_filtre_api(self):
        def titres(q):
            d = self.client.get(API + 'evenements/' + q).json()
            return [e['titre'] for e in (d['resultats'] if isinstance(d, dict) else d)]
        self.assertIn('Un sourire pour chaque orphelin', titres('?categorie=soutien'))
        self.assertNotIn('Un sourire pour chaque orphelin', titres('?categorie=tickets'))

    @mock.patch('Payments.fedapay.is_enabled', return_value=True)
    @mock.patch('Payments.fedapay.mode', return_value='demo')
    def test_soutien_sur_le_site_un_seul_ecran(self, *_):
        from Payments.models import Payment
        r = self.client.post(self.e.get_absolute_url(), {
            'montant': '2000', 'first_name': 'Ama', 'last_name': 'Koffi', 'country': 'tg', 'operator': 'togocel',
            'phone': '90000000', 'submission': 'x1'})
        self.assertEqual(r.status_code, 302, r.content[:400])
        p = Payment.objects.get(kind='soutien')
        self.assertEqual((p.amount, p.event_id), (2000, self.e.pk))


@override_settings(STORAGES=STORAGES)
class SaisiesTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email='v@example.com', password='x-Pass-12345', is_verified=True)
        self.e = Event.objects.create(title='Aide', description='x', location='Lomé', kind='soutien',
                                      starts_at=timezone.now() + timedelta(days=1))
        self.client.force_authenticate(self.user)

    def _payer(self, **kw):
        d = {'type': 'soutien', 'id': self.e.pk, 'montant': 1000, 'pays': 'tg', 'operateur': 'togocel',
             'telephone': '90000000'}
        d.update(kw)
        return self.client.post(API + 'paiements/', d, format='json')

    @mock.patch('Payments.fedapay.is_enabled', return_value=True)
    @mock.patch('Payments.fedapay.mode', return_value='demo')
    def test_saisies_refusees(self, *_):
        self.assertEqual(self._payer(telephone='kkkk90000000').status_code, 400)
        self.assertEqual(self._payer(telephone='9000').status_code, 400)
        self.assertEqual(self._payer(operateur='').status_code, 400)
        self.assertEqual(self._payer(telephone='96000000').status_code, 400)  # numéro Moov, opérateur Yas
        self.assertEqual(self._payer(montant=2_000_000).status_code, 400)
        self.assertEqual(self._payer(montant='abc').status_code, 400)
        self.assertEqual(self._payer().status_code, 201)

    def test_moyens_longueurs_et_prefixes(self):
        tg = next(p for p in self.client.get(API + 'paiements/moyens/').json()['pays'] if p['code'] == 'tg')
        self.assertEqual(tg['chiffres'], [8])
        self.assertIn('90', next(o for o in tg['operateurs'] if o['code'] == 'togocel')['prefixes'])

    def test_noms_du_site(self):
        from Payments.forms import CustomerForm
        f = CustomerForm({'first_name': 'Ama2', 'last_name': 'K', 'country': 'tg', 'operator': 'togocel',
                          'phone': '90000000', 'city': 'Lomé', 'whatsapp': '90000000'}, purpose='soutien')
        self.assertFalse(f.is_valid())
        self.assertIn('first_name', f.errors)
        self.assertIn('last_name', f.errors)  # 1 seule lettre
