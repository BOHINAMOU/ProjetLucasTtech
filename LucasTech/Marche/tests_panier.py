"""Panier de l'appli : prix recalculés par le serveur, une seule commande, formations débloquées une seule fois."""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from Formations.models import Formation, OrderItem
from Payments import services
from Payments.models import Payment
from Shop.models import PanierAppli, Product, ShopOrder

from .models import ReglageLivraison, Vendeur

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'


@override_settings(STORAGES=STORAGES)
@mock.patch('Payments.fedapay.is_enabled', return_value=True)
@mock.patch('Payments.fedapay.mode', return_value='demo')
class PanierTests(APITestCase):
    def setUp(self):
        U = get_user_model()
        self.u = U.objects.create_user(email='c@example.com', password='x-Pass-12345', first_name='Ama',
                                       last_name='Koffi', is_verified=True)
        ReglageLivraison.objects.create(tarif_base=500, prix_km=100, rayon_ville_km=25, distance_defaut_km=5)
        self.p1 = Product.objects.create(name='Clé USB', description='x', price=3000, stock=5)
        self.p2 = Product.objects.create(name='Livre', description='x', price=2000, stock=1, livrable=False)
        self.f = Formation.objects.create(author=self.u, title='Python', description='x', price=10000,
                                          formation_type='numerique', is_published=True)
        self.client.force_authenticate(self.u)

    def _arts(self, *extra):
        return [{'type': 'produit', 'id': self.p1.pk, 'quantite': 2, 'prix': 1},  # prix envoyé : ignoré
                {'type': 'produit', 'id': self.p2.pk, 'quantite': 9},
                {'type': 'formation', 'id': self.f.pk, 'quantite': 4}, *extra]

    def _payer(self, arts):
        d = {'type': 'panier', 'articles': arts, 'ville': 'Lomé', 'pays': 'tg', 'operateur': 'togocel',
             'telephone': '90000000'}
        return self.client.post(API + 'paiements/', d, format='json')

    def test_devis_prix_serveur(self, *_):
        r = self.client.post(API + 'paiements/devis/', {'type': 'panier', 'articles': self._arts(), 'ville': 'Lomé'},
                             format='json').json()
        # 2 × 3000 + 1 × 2000 (stock 1) + formation 10000 (quantité 1) ; livraison pour la clé seulement
        self.assertEqual((r['articles'], r['livraison'], r['total']), (18000, 1000, 19000))
        self.assertEqual([x['quantite'] for x in r['lignes']], [2, 1, 1])

    def test_paiement_commande_unique_et_formation_debloquee_une_fois(self, *_):
        r = self._payer(self._arts())
        self.assertEqual(r.status_code, 201, r.content)
        p = Payment.objects.get(reference=r.json()['reference'])
        self.assertEqual((p.kind, p.amount), ('shop', 19000))
        self.assertEqual(ShopOrder.objects.get(pk=p.shop_order_id).items.count(), 3)
        services.mark_paid(p)
        services.mark_paid(p)  # webhook + retour : rien en double
        self.assertEqual(Product.objects.get(pk=self.p1.pk).stock, 3)
        self.assertEqual(Product.objects.get(pk=self.p2.pk).stock, 0)
        acces = OrderItem.objects.filter(order__user=self.u, formation=self.f, order__status='paid')
        self.assertEqual(acces.count(), 1)
        self.assertEqual(ShopOrder.objects.get(pk=p.shop_order_id).status, 'paid')
        # un second panier avec la même formation ne crée pas un 2e accès
        r = self._payer([{'type': 'formation', 'id': self.f.pk}, {'type': 'produit', 'id': self.p1.pk}])
        services.mark_paid(Payment.objects.get(reference=r.json()['reference']))
        self.assertEqual(acces.count(), 1)

    def test_formation_non_payee_reste_bloquee(self, *_):
        self.assertEqual(self._payer([{'type': 'formation', 'id': self.f.pk}]).status_code, 201)
        self.assertFalse(OrderItem.objects.filter(order__user=self.u, formation=self.f, order__status='paid').exists())

    def test_vendeur_partenaire_a_part_et_indisponible(self, *_):
        vu = get_user_model().objects.create_user(email='v@example.com', password='x-Pass-12345')
        v = Vendeur.objects.create(user=vu, boutique='Chez Afi', whatsapp='22890112233', ville='Lomé',
                                   commission_pct=Decimal('10'), statut='valide')
        pv = Product.objects.create(name='Sac', description='x', price=5000, stock=5, vendeur=v, livrable=False)
        r = self.client.post(API + 'paiements/devis/', {'type': 'panier', 'ville': 'Lomé',
                             'articles': self._arts({'type': 'produit', 'id': pv.pk})}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('vendeur partenaire', r.json()['detail'])
        # un panier d'un seul vendeur partenaire : commission sur ses articles
        r = self._payer([{'type': 'produit', 'id': pv.pk, 'quantite': 2}])
        p = Payment.objects.get(reference=r.json()['reference'])
        self.assertEqual((p.vendeur, p.commission, p.amount), (v, 1000, 10000))
        self.p1.is_available = False
        self.p1.save()
        r = self.client.post(API + 'paiements/devis/', {'type': 'panier', 'articles': self._arts()}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('Clé USB', r.json()['detail'])
        r = self.client.post(API + 'paiements/devis/', {'type': 'panier', 'articles': []}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_panier_garde_sur_le_compte(self, *_):
        r = self.client.put(API + 'panier/', {'articles': [{'type': 'produit', 'id': self.p1.pk, 'quantite': 3},
                                                           {'type': 'formation', 'id': self.f.pk, 'quantite': 5},
                                                           {'type': 'pirate', 'id': 1}]}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['articles'], [{'type': 'produit', 'id': self.p1.pk, 'quantite': 3},
                                               {'type': 'formation', 'id': self.f.pk, 'quantite': 1}])
        self.assertEqual(PanierAppli.objects.get(user=self.u).contenu[0]['quantite'], 3)
        self.assertEqual(self.client.get(API + 'panier/').json()['articles'][1]['type'], 'formation')
