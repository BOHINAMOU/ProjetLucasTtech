import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from Shop.models import Product

from . import demandes
from .models import CategorieVendeur, DemandeVendeur, Vendeur

MEDIA = tempfile.mkdtemp()
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


@override_settings(MEDIA_ROOT=MEDIA, STORAGES=STORAGES, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class VendreTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)
        for f in Path(settings.PRIVATE_MEDIA_ROOT, 'vendeurs', 'pieces').glob('piece*'):
            f.unlink(missing_ok=True)

    def setUp(self):
        cache.clear()

    def _deposer(self, url='/vendre/', **extra):
        d = {'boutique': 'Chez Ama', 'activite': 'Pagnes', 'ville': 'Lomé', 'prenom': 'Ama', 'nom': 'Koffi',
             'telephone': '90000000', 'whatsapp': '+228 90 00 00 00', 'email': 'ama@example.com',
             'piece_type': 'passeport', 'piece_numero': 'P123',
             'piece': SimpleUploadedFile('piece.pdf', b'%PDF-1.4 test', content_type='application/pdf')}
        d.update(extra)
        return self.client.post(url, d)

    def test_demande_sans_compte_suivi_et_acceptation(self):
        self.assertEqual(self.client.get('/vendre/').status_code, 200)
        r = self._deposer()
        d = DemandeVendeur.objects.get()
        self.assertEqual(r['Location'], d.get_absolute_url())
        self.assertContains(self.client.get(d.get_absolute_url()), d.numero)
        self.assertEqual(self.client.get('/vendre/dossier/faux/').status_code, 404)
        self.assertEqual(self._deposer(whatsapp='kkk').status_code, 200)  # refusé
        v = demandes.accepter(d)
        self.assertEqual(v.statut, 'valide')
        self.assertTrue(v.user.is_staff)
        self.assertTrue(v.user.has_perm('Marche.add_categorievendeur'))

    def test_categories_privees_et_produits_du_vendeur(self):
        self._deposer()
        v = demandes.accepter(DemandeVendeur.objects.get())
        autre = Vendeur.objects.create(user=get_user_model().objects.create_user(email='b@example.com', password='x'),
                                       boutique='B', whatsapp='22891111111', ville='Kara', statut='valide')
        mienne = CategorieVendeur.objects.create(vendeur=v, nom='Pagnes wax')
        CategorieVendeur.objects.create(vendeur=autre, nom='Secret')
        v.user.set_password('x-Pass-12345')
        v.user.save()
        c = Client()
        c.force_login(v.user)
        page = c.get('/lantanteAdminTech/Marche/categorievendeur/').content.decode()
        self.assertIn('Pagnes wax', page)
        self.assertNotIn('Secret', page)
        r = c.post('/lantanteAdminTech/Shop/product/add/', {
            'categorie_vendeur': mienne.pk, 'name': 'Pagne', 'mode_commande': 'les_deux',
            'contact_whatsapp': '22890000000', 'livrable': 'on', 'description': 'Pagne', 'price': 3000, 'stock': 2,
            'is_available': 'on', 'images-TOTAL_FORMS': 0, 'images-INITIAL_FORMS': 0})
        self.assertEqual(r.status_code, 302, r.content[:800])
        p = Product.objects.get(name='Pagne')
        self.assertEqual((p.vendeur, p.categorie_vendeur, p.category.slug), (v, mienne, 'boutiques-partenaires'))

    def test_piece_reservee_a_l_equipe(self):
        self._deposer()
        d = DemandeVendeur.objects.get()
        self.assertIn(self.client.get(f'/vendre/piece/{d.pk}/').status_code, (302, 404))
        admin = get_user_model().objects.create_superuser(email='ad@example.com', password='x-Pass-12345')
        self.client.force_login(admin)
        r = self.client.get(f'/vendre/piece/{d.pk}/')
        self.assertEqual(r.status_code, 200)
        r.close()

    def test_correction_puis_renvoi(self):
        self._deposer()
        d = DemandeVendeur.objects.get()
        demandes.demander_correction(d, "Pièce illisible")
        url = f'/vendre/dossier/{d.jeton}/modifier/'
        self.assertContains(Client().get(url), 'Pièce illisible')
        self._deposer(url=url, piece=SimpleUploadedFile('piece2.pdf', b'%PDF-1.4 ok', content_type='application/pdf'))
        d.refresh_from_db()
        self.assertEqual(d.statut, 'en_attente')
        self.assertEqual(DemandeVendeur.objects.count(), 1)
