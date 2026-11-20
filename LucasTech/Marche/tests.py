"""Marketplace et codes promo : livraison, commission, accès vendeur, contrôles du code."""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from Payments import services
from Payments.models import CodePromo, Payment
from Shop.models import Product

from .livraison import haversine
from .models import ReglageLivraison, Reversement, Vendeur
from Marche.admin import comptes

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'
LOME = (6.1375, 1.2123)
KARA = (9.5511, 1.1861)


@override_settings(STORAGES=STORAGES)
@mock.patch('Payments.fedapay.is_enabled', return_value=True)
@mock.patch('Payments.fedapay.mode', return_value='demo')
class MarcheTests(APITestCase):
    def setUp(self):
        U = get_user_model()
        self.client_ = U.objects.create_user(email='c@example.com', password='x-Pass-12345', first_name='Ama',
                                             last_name='Koffi', is_verified=True)
        self.vu = U.objects.create_user(email='v@example.com', password='x-Pass-12345', is_verified=True)
        self.v = Vendeur.objects.create(user=self.vu, boutique='Chez Afi', whatsapp='22890112233', ville='Lomé',
                                        latitude=Decimal(str(LOME[0])), longitude=Decimal(str(LOME[1])),
                                        commission_pct=Decimal('10'), statut='valide')
        self.p = Product.objects.create(name='Sac', description='Sac', price=5000, stock=5, vendeur=self.v,
                                        livraison_autre_ville=2500)
        ReglageLivraison.objects.create(tarif_base=500, prix_km=100, rayon_ville_km=25, distance_defaut_km=5)
        self.client.force_authenticate(self.client_)

    def _mm(self, **extra):
        d = {'type': 'produit', 'id': self.p.pk, 'quantite': 2, 'pays': 'tg', 'operateur': 'togocel',
             'telephone': '90000000'}
        d.update(extra)
        return self.client.post(API + 'paiements/', d, format='json')

    def test_haversine(self, *_):
        self.assertAlmostEqual(haversine(*LOME, *KARA), 380, delta=15)

    def test_devis_meme_ville_par_km(self, *_):
        # ~3,3 km au nord du point de retrait
        r = self.client.post(API + 'paiements/devis/', {'type': 'produit', 'id': self.p.pk, 'quantite': 2,
                                                       'lat': 6.1675, 'lng': 1.2123}, format='json').json()
        self.assertEqual((r['articles'], r['livraison']), (10000, 900))  # 500 + 4 km x 100
        self.assertEqual(r['total'], 10900)

    def test_devis_ville_saisie_et_autre_ville(self, *_):
        r = self.client.post(API + 'paiements/devis/', {'type': 'produit', 'id': self.p.pk, 'ville': 'lome'},
                             format='json').json()
        self.assertEqual(r['livraison'], 1000)  # distance par défaut 5 km
        r = self.client.post(API + 'paiements/devis/', {'type': 'produit', 'id': self.p.pk, 'lat': KARA[0],
                                                       'lng': KARA[1]}, format='json').json()
        self.assertEqual(r['livraison'], 2500)  # prix fixe du vendeur
        self.p.livraison_autre_ville = None
        self.p.save()
        r = self.client.post(API + 'paiements/devis/', {'type': 'produit', 'id': self.p.pk, 'ville': 'Kara'},
                             format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'livraison'))
        r = self.client.post(API + 'paiements/devis/', {'type': 'produit', 'id': self.p.pk}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_paiement_commission_facture_et_sommes_dues(self, *_):
        r = self._mm(ville='Lomé')
        self.assertEqual(r.status_code, 201, r.content)
        p = Payment.objects.get(reference=r.json()['reference'])
        self.assertEqual((p.amount, p.livraison, p.commission, p.vendeur), (11000, 1000, 1000, self.v))
        services.mark_paid(p)
        self.assertEqual(Product.objects.get(pk=self.p.pk).stock, 3)
        d = self.client.get(f"{API}paiements/{p.reference}/").json()
        self.assertIn('/recu/', d['facture'])
        pdf = self.client.get(d['facture'].split('lantantetechnologie.com')[-1].split('testserver')[-1])
        self.assertEqual((pdf.status_code, pdf['Content-Type']), (200, 'application/pdf'))
        c = comptes(self.v)
        self.assertEqual((c['ventes'], c['du'], c['reste']), (1, 10000, 10000))  # 11 000 - 1 000 de commission
        Reversement.objects.create(vendeur=self.v, montant=4000, date=timezone.localdate())
        self.assertEqual(comptes(self.v)['reste'], 6000)

    def test_whatsapp_du_vendeur_et_vendeur_suspendu(self, *_):
        d = self.client.get(f"{API}boutique/produits/{self.p.pk}/").json()
        self.assertEqual((d['whatsapp'], d['vendeur'], d['livraison_vendeur']), ('22890112233', 'Chez Afi', True))
        self.v.statut = 'suspendu'
        self.v.save()
        self.assertEqual(self._mm(ville='Lomé').status_code, 400)

    def test_vendeur_sans_acces_a_l_admin_du_site(self, *_):
        # les vendeurs ont leur espace séparé (/espace/<code>/) ; plus d'accès à l'admin du site
        self.assertFalse(self.vu.is_staff)

    def test_code_pourcentage_sur_articles_pas_sur_livraison(self, *_):
        CodePromo.objects.create(code='rentree10', type='pct', valeur=10)
        r = self.client.post(API + 'paiements/devis/', {'type': 'produit', 'id': self.p.pk, 'quantite': 2,
                                                       'ville': 'Lomé', 'code_promo': ' Rentree10 '}, format='json').json()
        self.assertEqual((r['remise'], r['total'], r['code_promo']), (1000, 10000, 'RENTREE10'))
        r = self._mm(ville='Lomé', code_promo='RENTREE10')
        p = Payment.objects.get(reference=r.json()['reference'])
        self.assertEqual((p.amount, p.remise, p.code_promo.code), (10000, 1000, 'RENTREE10'))
        services.mark_paid(p)
        self.assertEqual(comptes(self.v)['du'], 10000)  # la remise est supportée par Lantante

    def test_code_controles(self, *_):
        now = timezone.now()
        CodePromo.objects.create(code='VIEUX', valeur=10, fin=now - timedelta(days=1))
        CodePromo.objects.create(code='GROS', valeur=10, minimum_achat=50000)
        c = CodePromo.objects.create(code='UNE', type='montant', valeur=500, max_utilisations=1, max_par_personne=None)
        autre = Product.objects.create(name='Autre', description='x', price=4000, stock=3)
        cible = CodePromo.objects.create(code='SACS', valeur=50)
        cible.produits.add(autre)
        for code, attendu in [('VIEUX', 'Code expiré'), ('GROS', 'dès'), ('INCONNU', 'Code invalide'),
                              ('SACS', 'Code non valable ici')]:
            r = self._mm(ville='Lomé', code_promo=code)
            self.assertEqual(r.status_code, 400, code)
            self.assertIn(attendu, r.json()['detail'])
            self.assertEqual(r.json()['code'], 'code_promo')
        self.assertEqual(self._mm(ville='Lomé', code_promo='UNE').status_code, 201)
        r = self._mm(ville='Lomé', code_promo='UNE')  # 1re utilisation encore en attente : réservée
        self.assertEqual(r.json()['detail'], 'Code épuisé')
        Payment.objects.filter(code_promo=c).update(status='canceled')
        self.assertEqual(self._mm(ville='Lomé', code_promo='UNE').status_code, 201)  # libéré
        self.assertEqual(Payment.objects.filter(code_promo__isnull=False).count(), 2)

    def test_code_par_personne_et_solde_et_recharge(self, *_):
        from Payments.solde import ajuster
        CodePromo.objects.create(code='MOI', type='montant', valeur=2000)  # 1 fois par personne par défaut
        ajuster(self.client_, 20000, 'test', None)
        r = self.client.post(API + 'paiements/', {'type': 'produit', 'id': self.p.pk, 'quantite': 1, 'ville': 'Lomé',
                                                  'moyen': 'solde', 'code_promo': 'MOI'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['montant'], 5000 + 1000 - 2000)
        r = self.client.post(API + 'paiements/', {'type': 'produit', 'id': self.p.pk, 'quantite': 1, 'ville': 'Lomé',
                                                  'moyen': 'solde', 'code_promo': 'MOI'}, format='json')
        self.assertEqual(r.json()['detail'], 'Code déjà utilisé')
        r = self.client.post(API + 'paiements/', {'type': 'depot', 'montant': 1000, 'pays': 'tg', 'operateur': 'togocel',
                                                  'telephone': '90000000', 'code_promo': 'MOI'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_code_ne_descend_pas_sous_100(self, *_):
        CodePromo.objects.create(code='TOUT', type='pct', valeur=100)
        r = self.client.post(API + 'paiements/devis/', {'type': 'produit', 'id': self.p.pk, 'ville': 'Lomé',
                                                       'code_promo': 'TOUT'}, format='json').json()
        self.assertEqual((r['remise'], r['total']), (5000, 1000))  # la livraison reste due


    def test_produit_non_livrable_et_depart_par_defaut(self, *_):
        formation = Product.objects.create(name='Cours PDF', description='x', price=2000, stock=9, livrable=False)
        r = self.client.post(API + 'paiements/devis/', {'type': 'produit', 'id': formation.pk}, format='json').json()
        self.assertEqual((r['livraison'], r['total']), (0, 2000))  # rien à livrer, pas de position demandée
        lantante = Product.objects.create(name='Clé USB', description='x', price=6000, stock=9,
                                          contact_whatsapp='22890000000')
        # 2 km au sud de l'Université de Lomé (point par défaut)
        r = self.client.post(API + 'paiements/devis/', {'type': 'produit', 'id': lantante.pk,
                                                       'lat': 6.1583, 'lng': 1.2128}, format='json').json()
        self.assertEqual((r['livraison'], r['total']), (700, 6700))
        r = self.client.post(API + 'paiements/devis/', {'type': 'produit', 'id': lantante.pk}, format='json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'livraison'))
        d = self.client.get(f"{API}boutique/produits/{lantante.pk}/").json()
        self.assertEqual((d['whatsapp'], d['livrable']), ('22890000000', True))
        self.assertFalse(self.client.get(f"{API}boutique/produits/{formation.pk}/").json()['livrable'])


from django.test import TestCase, override_settings  # noqa: E402


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class AccesVendeurTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from Marche.models import Vendeur
        from Shop.models import Product
        self.u = get_user_model().objects.create_user(email='vend@x.tg', password='Motdepasse-1')
        self.v = Vendeur.objects.create(user=self.u, boutique='Ma Boutique', whatsapp='22890000000', ville='Lomé', statut='valide')
        self.p = Product.objects.create(name='Sac rouge', price=5000, vendeur=self.v, stock=2)

    def test_lien_public_et_produits(self):
        self.assertEqual(self.v.slug, 'ma-boutique')
        r = self.client.get(self.v.lien_public())
        self.assertContains(r, 'Sac rouge')
        self.assertContains(r, 'wa.me/22890000000')

    def test_suspendre_masque_sans_effacer_puis_reactiver(self):
        from Marche.acces_vendeur import fin_pour, reactiver, suspendre
        from Shop.models import Product
        suspendre(self.v)
        self.assertContains(self.client.get(self.v.lien_public()), 'momentanément indisponible', status_code=503)
        self.assertFalse(Product.en_vente().filter(pk=self.p.pk).exists())
        self.assertTrue(Product.objects.filter(pk=self.p.pk, is_available=True).exists())  # rien d'effacé
        self.client.login(email='vend@x.tg', password='Motdepasse-1')
        r = self.client.get(f'/espace/{self.v.code}/tableau/')
        self.assertContains(r, 'suspendu', status_code=403)
        reactiver(self.v, fin_pour('3'))
        self.assertTrue(Product.en_vente().filter(pk=self.p.pk).exists())
        self.client.login(email='vend@x.tg', password='Motdepasse-1')
        self.assertEqual(self.client.get(f'/espace/{self.v.code}/tableau/').status_code, 200)

    def test_expiration_automatique_et_rappels(self):
        from datetime import timedelta
        from django.core import mail
        from django.utils import timezone
        from Marche.acces_vendeur import verifier_tous
        from Shop.models import Product
        t = timezone.localdate()
        self.v.fin_acces = t - timedelta(days=1)
        self.v.save()
        self.assertFalse(Product.en_vente().filter(pk=self.p.pk).exists())  # masqué dès le lendemain
        e, r = verifier_tous()
        self.v.refresh_from_db()
        self.assertEqual((e, self.v.statut), (1, 'expire'))
        self.assertTrue(mail.outbox)
        self.v.statut, self.v.fin_acces = 'valide', t + timedelta(days=7)
        self.v.save()
        self.assertEqual(verifier_tous()[1], 1)
        self.assertEqual(self.v.etat[0], 'bientot')

    def test_mon_lien(self):
        self.client.login(email='vend@x.tg', password='Motdepasse-1')
        r = self.client.get(f'/espace/{self.v.code}/mon-lien/')
        self.assertContains(r, '/vendeur/ma-boutique/')
        self.assertContains(r, 'Partager sur WhatsApp')


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class MiniSiteTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from Marche.models import SectionSite, Vendeur
        from Shop.models import Product
        self.u = get_user_model().objects.create_user(email='ms@x.tg', password='Motdepasse-1')
        self.v = Vendeur.objects.create(user=self.u, boutique='Mode Ama', whatsapp='22890000000', ville='Lomé',
                                        statut='valide', slogan='Le pagne autrement', couleur='#AA3366')
        SectionSite.objects.create(vendeur=self.v, titre='Notre histoire', texte='Depuis 2015.')
        self.p = Product.objects.create(name='Robe wax', price=15000, vendeur=self.v, stock=2)

    def test_pages_du_mini_site(self):
        r = self.client.get('/vendeur/mode-ama/')
        self.assertContains(r, 'Le pagne autrement')
        self.assertContains(r, 'Notre histoire')
        self.assertContains(r, '#AA3366')
        self.assertNotContains(r, 'Monétisation')  # aucun menu Lantante
        self.assertContains(self.client.get('/vendeur/mode-ama/produits/?q=robe'), 'Robe wax')
        r = self.client.get(f'/vendeur/mode-ama/produits/{self.p.pk}/')
        self.assertContains(r, 'Commander sur WhatsApp')
        self.assertContains(self.client.get('/vendeur/mode-ama/contact/'), 'wa.me/22890000000')

    def test_chaine_et_reseaux(self):
        r = self.client.get('/vendeur/mode-ama/')
        self.assertNotContains(r, 'Rejoindre ma chaîne')  # rien d'affiché si non renseigné
        self.v.chaine_whatsapp = 'https://whatsapp.com/channel/abc'
        self.v.instagram = 'https://instagram.com/modeama'
        self.v.save()
        r = self.client.get('/vendeur/mode-ama/')
        self.assertContains(r, 'https://whatsapp.com/channel/abc')
        self.assertContains(r, 'Rejoindre ma chaîne WhatsApp')
        self.assertContains(r, 'https://instagram.com/modeama')
        self.assertNotContains(r, 'aria-label="Facebook"')

    def test_ancienne_adresse_et_espace(self):
        r = self.client.get('/shop/vendeur/mode-ama/')
        self.assertEqual((r.status_code, r['Location']), (301, '/vendeur/mode-ama/'))
        r = self.client.get('/s/mode-ama/produits/?q=robe')
        self.assertEqual((r.status_code, r['Location']), (301, '/vendeur/mode-ama/produits/?q=robe'))
        self.client.login(email='ms@x.tg', password='Motdepasse-1')
        r = self.client.get(f'/espace/{self.v.code}/mon-site/')
        self.assertContains(r, 'Sections de l')
        data = {'site-boutique': 'Mode Ama', 'site-slogan': 'Nouveau slogan', 'site-couleur': '#112233',
                'site-whatsapp': '90000000', 'site-ville': 'Lomé', 'site-description': '', 'site-telephone': '',
                'site-email_contact': '', 'site-adresse_retrait': '', 'site-facebook': '', 'site-instagram': '', 'site-tiktok': '',
                'sec-TOTAL_FORMS': '2', 'sec-INITIAL_FORMS': '1', 'sec-MIN_NUM_FORMS': '0', 'sec-MAX_NUM_FORMS': '8',
                'sec-0-id': str(self.v.sections.first().pk), 'sec-0-titre': 'Notre histoire', 'sec-0-texte': 'x', 'sec-0-ordre': '1',
                'sec-1-titre': 'Livraison', 'sec-1-texte': 'Partout à Lomé', 'sec-1-ordre': '2'}
        r = self.client.post(f'/espace/{self.v.code}/mon-site/', data)
        self.assertEqual(r.status_code, 302)
        self.v.refresh_from_db()
        self.assertEqual((self.v.slogan, self.v.couleur, self.v.sections.count()), ('Nouveau slogan', '#112233', 2))
