"""Catalogue de l'application : listes paginées + recherche, détails, carrousel, accueil en un appel,
version de l'application, ouverture de session web (paiement dans l'appli) et compression gzip."""
import io
import json
import os
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase

TMP = tempfile.mkdtemp()
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'


def jpeg(name='photo.jpg', size=(1200, 800)):
    buf = io.BytesIO()
    Image.new('RGB', size, (20, 120, 70)).save(buf, 'JPEG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT=TMP, STORAGES=STORAGES)
class CatalogueTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        from Events.models import Event, TicketType
        from Formations.models import Formation
        from Publications.models import Publication
        from Services.models import Service
        from Shop.models import Category, Product, ProductImage
        from core.models import Partner
        U = get_user_model()
        self.user = U.objects.create_user(email='eleve@example.com', password='x-Pass-12345')
        self.cat = Category.objects.create(name='Téléphones', slug='telephones')
        self.produits = [Product.objects.create(name=f'Téléphone {i}', category=self.cat, price=10000 + i,
                                                old_price=20000, stock=3, description='<p>Super <b>téléphone</b></p>',
                                                image=jpeg()) for i in range(25)]
        ProductImage.objects.create(product=self.produits[0], image=jpeg('g.jpg'))
        Product.objects.create(name='Casque', price=5000, stock=0, is_available=True)
        Product.objects.create(name='Retiré', price=1, is_available=False)
        self.formation = Formation.objects.create(author=self.user, title='Python', description='<p>Bases</p>',
                                                  price=8000, old_price=20000, image=jpeg(),
                                                  formation_type='numerique')
        self.service = Service.objects.create(admin=self.user, title='Site web', description='Création', price=50000,
                                              image=jpeg())
        self.pub = Publication.objects.create(author=self.user, title='Rentrée', content='<p>Infos</p>',
                                              is_published=True, cover_image=jpeg())
        Publication.objects.create(author=self.user, title='Brouillon', content='x', is_published=False)
        self.partner = Partner.objects.create(name='Togocom', logo=jpeg(), description='Opérateur')
        self.event = Event.objects.create(title='Festival', description='Musique', location='Lomé',
                                          starts_at=timezone.now() + timedelta(days=5), cover=jpeg())
        TicketType.objects.create(event=self.event, name='VIP', price=5000, quantity=10)

    def test_produits_pagines_recherche_et_categorie(self):
        r = self.client.get(API + 'boutique/produits/', {'page': 1})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual((len(d['resultats']), d['total'], d['pages'], d['suivant']), (20, 26, 2, True))
        p = next(x for x in d['resultats'] if x['titre'].startswith('Téléphone'))
        self.assertEqual(p['prix_barre'], 20000)
        self.assertGreater(p['remise'], 0)
        self.assertTrue(p['image_vignette'].endswith('.webp'))
        self.assertEqual(len(self.client.get(API + 'boutique/produits/', {'page': 2}).json()['resultats']), 6)
        self.assertEqual(self.client.get(API + 'boutique/produits/', {'q': 'casque', 'page': 1}).json()['total'], 1)
        self.assertEqual(self.client.get(API + 'boutique/produits/',
                                         {'categorie': 'telephones', 'page': 1}).json()['total'], 25)
        # compatibilité appli 1.0 : liste simple sans ?page
        self.assertIsInstance(self.client.get(API + 'boutique/produits/').json(), list)
        self.assertIn('public', r['Cache-Control'])

    def test_vignette_reduite(self):
        p = next(x for x in self.client.get(API + 'boutique/produits/', {'page': 1}).json()['resultats']
                 if x['titre'].startswith('Téléphone'))
        path = os.path.join(TMP, p['image_vignette'].split('/media/', 1)[1])
        with Image.open(path) as im:
            self.assertLessEqual(max(im.size), 400)

    def test_detail_produit_galerie_et_paiement(self):
        d = self.client.get(f'{API}boutique/produits/{self.produits[0].pk}/').json()
        self.assertEqual(len(d['images']), 2)
        self.assertEqual(d['description'], 'Super téléphone')
        self.assertIn('/paiement/produit/', d['url_paiement'])
        self.assertEqual(self.client.get(f'{API}boutique/produits/999999/').status_code, 404)

    def test_details_formation_service_publication_partenaire_evenement(self):
        f = self.client.get(f'{API}formations/{self.formation.pk}/').json()
        self.assertEqual((f['prix'], f['prix_barre'], f['remise']), (8000, 20000, 60))
        self.assertIn('/paiement/formation/', f['url_paiement'])
        s = self.client.get(f'{API}services/{self.service.pk}/').json()
        self.assertIn('/paiement/service/', s['url_paiement'])
        self.assertEqual(self.client.get(API + 'services/', {'q': 'site'}).json()[0]['titre'], 'Site web')
        pubs = self.client.get(API + 'publications/', {'page': 1}).json()
        self.assertEqual(pubs['total'], 1)
        self.assertEqual(self.client.get(f'{API}publications/{self.pub.pk}/').json()['contenu'], 'Infos')
        self.assertEqual(self.client.get(f'{API}partenaires/{self.partner.pk}/').json()['nom'], 'Togocom')
        e = self.client.get(f'{API}evenements/{self.event.pk}/').json()
        self.assertEqual(e['tickets'][0]['nom'], 'VIP')
        self.assertEqual(e['tickets'][0]['restant'], 10)

    def test_accueil_en_un_appel_avec_carrousel(self):
        d = self.client.get(API + 'home/').json()
        for key in ('carrousel', 'concours_populaires', 'evenements', 'formations', 'produits', 'services',
                    'actualites'):
            self.assertIn(key, d)
        types = {x['type'] for x in d['carrousel']}
        self.assertTrue({'produit', 'formation', 'service', 'publication', 'evenement', 'partenaire'} <= types)
        self.assertTrue(all(x['image'] and x['type_libelle'] for x in d['carrousel']))

    def test_gzip_api(self):
        r = self.client.get(API + 'boutique/produits/', HTTP_ACCEPT_ENCODING='gzip')
        self.assertEqual(r['Content-Encoding'], 'gzip')
        self.assertFalse(self.client.get('/', HTTP_ACCEPT_ENCODING='gzip').has_header('Content-Encoding'))

    def test_version(self):
        self.assertEqual(self.client.get(API + 'version/').status_code, 404)
        os.makedirs(os.path.join(TMP, 'app'), exist_ok=True)
        with open(os.path.join(TMP, 'app', 'version.json'), 'w', encoding='utf-8') as fh:
            json.dump({'version': '1.1.0', 'build': 3, 'taille': 123, 'notes': 'Carrousel',
                       'obligatoire': False}, fh)
        d = self.client.get(API + 'version/').json()
        self.assertEqual((d['version'], d['build'], d['obligatoire']), ('1.1.0', 3, False))
        self.assertTrue(d['url_apk'].endswith('/media/app/Lantante.apk'))

    def test_session_web_pour_paiement_dans_l_appli(self):
        self.assertEqual(self.client.get(API + 'auth/web/', {'suivant': '/paiement/'}).status_code, 401)
        token = self.client.post(API + 'auth/login/', {'identifiant': 'eleve@example.com',
                                                        'password': 'x-Pass-12345'}, format='json').json()['token']
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)
        r = self.client.get(API + 'auth/web/', {'suivant': f'/paiement/formation/{self.formation.pk}/'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r['Location'], f'/paiement/formation/{self.formation.pk}/')
        self.assertIn('sessionid', r.cookies)
        # pas de redirection vers un autre site
        self.assertEqual(self.client.get(API + 'auth/web/', {'suivant': 'https://evil.example/'})['Location'], '/')
        self.assertEqual(self.client.get(API + 'auth/web/', {'suivant': '//evil.example/'})['Location'], '/')
