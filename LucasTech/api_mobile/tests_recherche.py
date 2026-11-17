from django.test import TestCase
from rest_framework.test import APIClient

from Ecoles.models import Ecole

from .recherche import score, sigle


class RechercheTests(TestCase):
    def setUp(self):
        Ecole.objects.create(nom="Université de Lomé", slug='ul', type='universite', ville='Lomé', alias='UL, Univ Lomé')
        Ecole.objects.create(nom="Université de Kara", slug='uk', type='universite', ville='Kara')
        Ecole.objects.create(nom="Institut Africain d'Informatique", slug='iai', type='universite', ville='Lomé')
        Ecole.objects.create(nom="Lycée de Tokoin", slug='tokoin', type='lycee', ville='Lomé')
        self.c = APIClient()

    def noms(self, q):
        r = self.c.get('/api/mobile/v1/ecoles/', {'q': q})
        d = r.json()
        return [e['nom'] for e in (d['resultats'] if isinstance(d, dict) else d)]

    def test_sigles(self):
        self.assertEqual(sigle("Université de Lomé"), 'ul')
        self.assertEqual(sigle("Institut Africain d'Informatique"), 'iai')
        self.assertEqual(self.noms('UL')[0], "Université de Lomé")
        self.assertEqual(self.noms('ul')[0], "Université de Lomé")
        self.assertEqual(self.noms('UK')[0], "Université de Kara")
        self.assertEqual(self.noms('IAI')[0], "Institut Africain d'Informatique")

    def test_sans_accents_ni_majuscules(self):
        self.assertIn("Université de Lomé", self.noms('lome'))
        self.assertEqual(self.noms('universite de lome')[0], "Université de Lomé")
        self.assertEqual(self.noms('LYCEE')[0], "Lycée de Tokoin")

    def test_faute_de_frappe(self):
        self.assertEqual(self.noms('Univrsité de Lomé')[0], "Université de Lomé")
        self.assertIn("Lycée de Tokoin", self.noms('tokoim'))

    def test_pertinence_et_vide(self):
        self.assertGreater(score('ul', "Université de Lomé"), score('ul', "Culture urbaine"))
        self.assertEqual(self.noms('zzzz'), [])

    def test_recherche_globale(self):
        r = self.c.get('/api/mobile/v1/recherche/', {'q': 'UL'})
        self.assertEqual(r.json()['groupes'][0]['type'], 'ecole')
        ecoles = [g for g in r.json()['groupes'] if g['type'] == 'ecole']
        self.assertEqual(ecoles[0]['resultats'][0]['nom'], "Université de Lomé")


class ModeCommandeTests(TestCase):
    def test_mode_commande_dans_l_api(self):
        from Shop.models import Category, Product
        cat = Category.objects.create(name='Divers', slug='divers')
        p = Product.objects.create(name='Sac', price=5000, stock=3, category=cat, mode_commande='whatsapp',
                                   contact_whatsapp='22890000000')
        d = APIClient().get(f'/api/mobile/v1/boutique/produits/{p.pk}/').json()
        self.assertEqual(d['mode_commande'], 'whatsapp')
        self.assertIsNone(d['url_paiement'])
        self.assertTrue(d['lien'].startswith('http'))
        self.assertEqual(d['whatsapp'], '22890000000')
        from core.models import SiteSettings
        st = SiteSettings.load(); st.whatsapp_1 = '22892967700'; st.save()
        d = APIClient().get(f'/api/mobile/v1/boutique/produits/{p.pk}/').json()
        self.assertEqual(d['whatsapp_commande'], '22892967700')  # Lantante, pas le contact du produit
