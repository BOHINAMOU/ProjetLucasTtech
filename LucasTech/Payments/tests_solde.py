"""Solde Lantante (dépôt seul) : crédit unique, débit protégé, pas de solde négatif, traces."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import override_settings
from rest_framework.test import APITestCase

from . import services
from .models import MouvementSolde, Payment, Portefeuille
from .solde import SoldeInsuffisant, ajuster, payer_avec_solde, portefeuille

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'


@override_settings(STORAGES=STORAGES)
class SoldeTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email='s@example.com', password='x-Pass-12345',
                                                         first_name='Ama', last_name='Koffi', is_verified=True)
        self.client.force_authenticate(self.user)

    def _depot(self, montant=2000):
        return Payment.objects.create(user=self.user, kind='depot', amount=montant, description='Recharge',
                                      first_name='Ama', last_name='Koffi', phone='+22890000000', mode='sandbox')

    def test_double_webhook_un_seul_credit(self):
        p = self._depot()
        services.mark_paid(p)
        services.mark_paid(p)  # 2e webhook
        from .solde import crediter_depot
        crediter_depot(p)  # 3e appel direct
        self.assertEqual(portefeuille(self.user).solde, 2000)
        self.assertEqual(MouvementSolde.objects.filter(payment=p).count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MouvementSolde.objects.create(portefeuille=portefeuille(self.user), type='depot', montant=2000,
                                          solde_apres=4000, payment=p)

    def test_depot_non_paye_ne_credite_rien(self):
        self._depot()
        self.assertEqual(portefeuille(self.user).solde, 0)

    @mock.patch('Payments.fedapay.is_enabled', return_value=True)
    @mock.patch('Payments.fedapay.mode', return_value='demo')
    def test_recharge_par_api_et_montants(self, *_):
        r = self.client.post(API + 'paiements/', {'type': 'depot', 'montant': 50, 'pays': 'tg', 'operateur': 'togocel',
                                                  'telephone': '90000000'}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.post(API + 'paiements/', {'type': 'depot', 'montant': 1500, 'pays': 'tg', 'operateur': 'togocel',
                                                  'telephone': '90000000'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.client.get(API + 'solde/').json()['solde'], 0)  # pas encore confirmé
        services.mark_paid(Payment.objects.get(reference=r.json()['reference']))
        d = self.client.get(API + 'solde/').json()
        self.assertEqual((d['solde'], d['mouvements'][0]['type']), (1500, 'depot'))

    def test_payer_avec_solde_et_solde_insuffisant(self):
        from concours.models import Contest, ContestCategory
        cat = ContestCategory.objects.get(slug='enseignement')
        c = Contest.objects.create(acronym='IAI', name='IAI', category=cat, is_published=True, access_price=1000)
        r = self.client.post(API + 'paiements/', {'type': 'concours', 'id': c.pk, 'moyen': 'solde'}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'solde_insuffisant'))
        self.assertFalse(Payment.objects.filter(kind='concours').exists())  # rien de créé
        services.mark_paid(self._depot(1500))
        r = self.client.post(API + 'paiements/', {'type': 'concours', 'id': c.pk, 'moyen': 'solde'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['statut'], 'paye')
        self.assertEqual(portefeuille(self.user).solde, 500)
        from abonnements.access import user_can_access
        self.assertTrue(user_can_access(self.user, c))
        h = self.client.get(f"{API}historique/paiement-{r.json()['reference']}/").json()
        self.assertEqual(h['moyen'], 'Solde Lantante')

    def test_jamais_negatif_meme_en_rafale(self):
        services.mark_paid(self._depot(1000))
        p = Payment.objects.create(user=self.user, kind='service', amount=800, description='x', first_name='A',
                                   last_name='K', phone='', mode='solde')
        payer_avec_solde(self.user, 800, p)
        p2 = Payment.objects.create(user=self.user, kind='service', amount=800, description='y', first_name='A',
                                    last_name='K', phone='', mode='solde')
        with self.assertRaises(SoldeInsuffisant):
            payer_avec_solde(self.user, 800, p2)
        self.assertEqual(Portefeuille.objects.get(user=self.user).solde, 200)
        # le solde est toujours égal à la somme des mouvements
        pf = portefeuille(self.user)
        self.assertEqual(pf.solde, sum(pf.mouvements.values_list('montant', flat=True)))

    def test_ajustement_motive_et_pas_de_retrait(self):
        admin = get_user_model().objects.create_superuser(email='adm@example.com', password='x-Pass-12345')
        with self.assertRaises(ValueError):
            ajuster(self.user, 500, '  ', admin)
        m = ajuster(self.user, 500, 'Geste commercial', admin)
        self.assertEqual((m.solde_apres, m.par), (500, admin))
        with self.assertRaises(SoldeInsuffisant):
            ajuster(self.user, -600, 'Correction', admin)
        self.assertEqual(self.client.post(API + 'solde/retrait/', {'montant': 100}, format='json').status_code, 404)

    def test_admin_ajustement_et_liste(self):
        admin = get_user_model().objects.create_superuser(email='adm2@example.com', password='x-Pass-12345')
        self.client.force_login(admin)
        url = '/lantanteAdminTech/Payments/mouvementsolde/add/'
        self.assertEqual(self.client.get(url).status_code, 200)
        r = self.client.post(url, {'utilisateur': self.user.pk, 'montant': -50, 'motif': 'x'})
        self.assertEqual(r.status_code, 200)  # refusé : deviendrait négatif
        r = self.client.post(url, {'utilisateur': self.user.pk, 'montant': 300, 'motif': 'Bonus'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(portefeuille(self.user).solde, 300)
        self.assertEqual(self.client.get('/lantanteAdminTech/Payments/portefeuille/').status_code, 200)
        pf = portefeuille(self.user)
        self.assertEqual(self.client.get(f'/lantanteAdminTech/Payments/portefeuille/{pf.pk}/change/').status_code, 200)
