import io
import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from .models import DemandeLogement, Logement

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/logements/'


def photo(nom='p.jpg', fmt='JPEG'):
    b = io.BytesIO()
    Image.new('RGB', (40, 30), (20, 120, 60)).save(b, fmt)
    return SimpleUploadedFile(nom, b.getvalue(), content_type='image/jpeg')


DONNEES = {'type': 'chambre_salon', 'quartier': 'Adidogomé', 'ville': 'Lomé', 'loyer': '35000', 'description': 'Propre, eau et courant.',
           'proprietaire_nom': 'Kofi', 'proprietaire_telephone': '90 11 22 33', 'propose_par_role': 'proprietaire',
           'accord': 'on', 'equipements': ['clim', 'cuisine']}


@override_settings(STORAGES=STORAGES, MEDIA_ROOT=tempfile.mkdtemp())
class PropositionTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_publier_en_attente_jamais_visible_avant_validation(self):
        r = self.client.post('/location/publier/', {**DONNEES, 'photos': [photo('a.jpg'), photo('b.png', 'PNG')]})
        self.assertEqual(r.status_code, 302, r.content[:600])
        l = Logement.objects.get()
        self.assertEqual((l.statut, l.photos.count(), l.proprietaire_telephone, l.equipements),
                         ('attente', 2, '22890112233', ['clim', 'cuisine']))
        self.assertNotContains(self.client.get('/location/'), 'Adidogomé')
        self.assertEqual(self.client.get(f'/location/{l.pk}/').status_code, 404)
        self.assertEqual(self.client.get(API).json()['resultats'], [])
        self.assertEqual(self.client.get(f'{API}{l.pk}/').status_code, 404)
        l.statut = 'publie'
        l.save()
        self.assertContains(self.client.get('/location/'), 'Adidogomé')
        self.assertEqual(len(self.client.get(API).json()['resultats']), 1)

    def test_publier_refuse_sans_photo_faux_fichier_ou_piege(self):
        self.assertContains(self.client.post('/location/publier/', DONNEES), 'Ajoutez au moins une photo')
        faux = SimpleUploadedFile('x.jpg', b'pas une image', content_type='image/jpeg')
        self.assertContains(self.client.post('/location/publier/', {**DONNEES, 'photos': [faux]}), "pas une photo")
        trop = [photo(f'{i}.jpg') for i in range(9)]
        self.assertContains(self.client.post('/location/publier/', {**DONNEES, 'photos': trop}), '8 photos maximum')
        self.client.post('/location/publier/', {**DONNEES, 'photos': [photo()], 'site_internet': 'spam'})
        self.assertFalse(Logement.objects.exists())

    def test_je_cherche_site_et_api(self):
        r = self.client.post('/location/je-cherche/', {'nom': 'Ama', 'telephone': '+228 91 00 00 00', 'type': 'chambre',
                                                       'lieu': 'Agoè', 'budget': '25000'})
        self.assertEqual(r.status_code, 302)
        d = DemandeLogement.objects.get()
        self.assertEqual((d.telephone, d.statut), ('22891000000', 'nouvelle'))
        r = self.client.post(API + 'demande/', {'nom': 'Yao', 'telephone': '92000000', 'type': 'maison', 'lieu': 'Kara',
                                                'budget': 60000}, format='json', content_type='application/json')
        self.assertEqual(r.status_code, 201, r.content)
        r = self.client.post(API + 'demande/', {'nom': 'Yao', 'telephone': '12', 'type': 'maison', 'lieu': 'Kara',
                                                'budget': 60000}, content_type='application/json')
        self.assertEqual((r.status_code, r.json()['code']), (400, 'formulaire'))

    def test_api_proposer_multipart_et_limite(self):
        r = self.client.post(API + 'proposer/', {**DONNEES, 'photos': [photo()]})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Logement.objects.get().statut, 'attente')
        for _ in range(5):
            self.client.post(API + 'proposer/', {**DONNEES, 'photos': [photo()]})
        self.assertEqual(self.client.post(API + 'proposer/', {**DONNEES, 'photos': [photo()]}).status_code, 429)
        self.assertEqual(self.client.get(API + 'options/').json()['max_photos'], 8)

    def test_liste_vide_montre_les_deux_boutons(self):
        r = self.client.get('/location/')
        self.assertContains(r, 'Je cherche un logement</a>', count=1)
        self.assertContains(r, 'Publier mon logement</a>', count=1)

    def test_admin_valider_et_a_traiter(self):
        U = get_user_model()
        a = U.objects.create_superuser(email='admin@example.com', password='x-Pass-12345')
        self.client.force_login(a)
        l = Logement.objects.create(type='studio', ville='Lomé', quartier='Bè', loyer=40000, statut='attente')
        DemandeLogement.objects.create(nom='Ama', telephone='22891000000', type='chambre', lieu='Agoè', budget=25000)
        self.assertContains(self.client.get('/lantanteAdminTech/a-traiter/'), 'À valider')
        self.client.post('/lantanteAdminTech/Logements/logement/', {'action': 'valider', '_selected_action': [l.pk]})
        l.refresh_from_db()
        self.assertEqual(l.statut, 'publie')
        d = DemandeLogement.objects.get()
        self.assertContains(self.client.get(f'/lantanteAdminTech/Logements/demandelogement/{d.pk}/change/'), 'wa.me/22891000000')
