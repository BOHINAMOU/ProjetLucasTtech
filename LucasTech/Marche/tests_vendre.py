import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from Payments.models import Payment
from Shop.models import Product

from .espace import envoyer_acces
from .models import CategorieVendeur, Vendeur

MEDIA = tempfile.mkdtemp()
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


@override_settings(MEDIA_ROOT=MEDIA, STORAGES=STORAGES, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EspaceVendeurTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_superuser(email='ad@example.com', password='x-Pass-12345')

    def _creer(self, email='ama@example.com'):
        c = Client()
        c.force_login(self.admin)
        r = c.post('/lantanteAdminTech/Marche/vendeur/add/', {
            'boutique': 'Chez Ama', 'email': email, 'whatsapp': '+228 90 11 22 33', 'ville': 'Lomé', 'commission_pct': '10'})
        self.assertEqual(r.status_code, 302, r.content[:600])
        return Vendeur.objects.get(user__email=email)

    def _activer(self, v, mdp='Motdepasse-123'):
        v.refresh_from_db()
        c = Client()
        r = c.post(f'/espace/{v.code}/activer/{v.activation}/', {'password': mdp, 'password2': mdp})
        self.assertEqual(r.status_code, 302)
        return c

    def test_contact_sans_formulaire(self):
        from core.models import SiteSettings
        st = SiteSettings.load(); st.whatsapp_1 = '22892967700'; st.save()
        page = self.client.get('/vendre/').content.decode()
        self.assertIn('wa.me/22892967700', page)
        self.assertNotIn('<form', page.split('rp-banniere')[1].split('</main>')[0])

    def test_creation_par_admin_activation_et_connexion(self):
        v = self._creer()
        self.assertEqual(v.statut, 'valide')
        self.assertFalse(v.user.is_staff)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f'/espace/{v.code}/activer/', mail.outbox[0].body)
        # le lien seul ne donne pas accès
        self.assertEqual(Client().get(f'/espace/{v.code}/tableau/')['Location'], f'/espace/{v.code}/')
        c = self._activer(v)
        self.assertEqual(c.get(f'/espace/{v.code}/tableau/').status_code, 200)
        v.refresh_from_db()
        self.assertEqual(v.activation, '')  # lien d'activation à usage unique
        # connexion normale
        c2 = Client()
        r = c2.post(f'/espace/{v.code}/', {'email': 'ama@example.com', 'password': 'Motdepasse-123'})
        self.assertEqual(r['Location'], f'/espace/{v.code}/tableau/')
        page = c2.get(f'/espace/{v.code}/tableau/').content.decode()
        self.assertNotIn('lt-footer', page)  # aucun élément du site

    def test_limite_de_tentatives(self):
        v = self._creer()
        self._activer(v)
        c = Client()
        for _ in range(5):
            c.post(f'/espace/{v.code}/', {'email': 'ama@example.com', 'password': 'faux'})
        r = c.post(f'/espace/{v.code}/', {'email': 'ama@example.com', 'password': 'Motdepasse-123'})
        self.assertContains(r, 'Trop de tentatives')

    def test_vendeur_ne_voit_que_ses_donnees_et_produits(self):
        v = self._creer()
        autre = self._creer('b@example.com')
        c = self._activer(v)
        self.assertEqual(c.get(f'/espace/{autre.code}/tableau/')['Location'], f'/espace/{autre.code}/')
        c.post(f'/espace/{v.code}/categories/', {'nom': 'Pagnes wax'})
        cat = CategorieVendeur.objects.get(vendeur=v)
        CategorieVendeur.objects.create(vendeur=autre, nom='Secret')
        self.assertNotContains(c.get(f'/espace/{v.code}/categories/'), 'Secret')
        r = c.post(f'/espace/{v.code}/produits/ajouter/', {
            'name': 'Pagne', 'categorie_vendeur': cat.pk, 'price': 3000, 'description': 'Beau pagne', 'stock': 2,
            'is_available': 'on', 'mode_commande': 'les_deux', 'contact_whatsapp': '', 'livrable': 'on'})
        self.assertEqual(r.status_code, 302, r.content[:800])
        p = Product.objects.get(name='Pagne')
        self.assertEqual((p.vendeur, p.categorie_vendeur, p.category.slug), (v, cat, 'boutiques-partenaires'))
        # WhatsApp vide : celui des paramètres du vendeur pour la commande
        d = Client().get(f'/api/mobile/v1/boutique/produits/{p.pk}/').json()
        self.assertEqual(d['whatsapp_commande'], '22890112233')
        p.refresh_from_db()
        self.assertEqual(p.vues, 1)
        Client().post(f'/api/mobile/v1/boutique/produits/{p.pk}/whatsapp/')
        self.assertContains(c.get(f'/espace/{v.code}/tableau/'), 'Clics WhatsApp')
        p2 = Product.objects.create(name='Autre', price=1, stock=1, vendeur=autre)
        self.assertEqual(c.get(f'/espace/{v.code}/produits/{p2.pk}/').status_code, 404)
        c.post(f'/espace/{v.code}/produits/{p.pk}/supprimer/')
        self.assertFalse(Product.objects.filter(pk=p.pk).exists())

    def test_vendeur_suspendu_et_lien_regenere(self):
        v = self._creer()
        c = self._activer(v)
        Vendeur.objects.filter(pk=v.pk).update(statut='suspendu')
        self.assertContains(c.get(f'/espace/{v.code}/tableau/'), 'suspendu', status_code=403)
        ancien = v.code
        a = Client()
        a.force_login(self.admin)
        a.post('/lantanteAdminTech/Marche/vendeur/', {'action': 'regenerer_lien', '_selected_action': [v.pk]})
        v.refresh_from_db()
        self.assertNotEqual(v.code, ancien)
        self.assertEqual(Client().get(f'/espace/{ancien}/').status_code, 404)
        self.assertFalse(Payment.objects.exists())
