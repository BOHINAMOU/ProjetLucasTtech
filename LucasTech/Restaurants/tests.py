import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .models import GroupeOptions, Plat, Restaurant, lire_options

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/restaurants/'


@override_settings(STORAGES=STORAGES, MEDIA_ROOT=tempfile.mkdtemp())
class RestaurantsTests(TestCase):
    def setUp(self):
        self.r = Restaurant.objects.create(nom='Chez Test', quartier='Bè', whatsapp='90 11 22 33', horaires='10 h – 22 h')
        self.p = Plat.objects.create(restaurant=self.r, nom='Riz sauce arachide', prix=1500)
        GroupeOptions.objects.create(restaurant=self.r, plat=self.p, nom='Accompagnements', choix='multiple',
                                     options_texte="Alloco | 500\nFrites = 700\nSans piment")
        GroupeOptions.objects.create(restaurant=self.r, nom='Boissons', choix='unique', options_texte="Coca 33 cl | 500\nEau 1,5 L 300")
        Plat.objects.create(restaurant=self.r, nom='Caché', prix=1000, disponible=False)

    def test_lecture_des_options(self):
        self.assertEqual(lire_options("Alloco | 500\nCoca 33 cl = 500\nEau 1,5 L 300\nSans piment\n\n"),
                         [{'nom': 'Alloco', 'prix': 500}, {'nom': 'Coca 33 cl', 'prix': 500},
                          {'nom': 'Eau 1,5 L', 'prix': 300}, {'nom': 'Sans piment', 'prix': 0}])

    def test_api_liste_et_fiche_avec_options(self):
        self.assertEqual([x['nom'] for x in self.client.get(API).json()['resultats']], ['Chez Test'])
        d = self.client.get(f'{API}{self.r.slug}/').json()
        self.assertEqual(d['whatsapp'], '22890112233')
        self.assertEqual([p['nom'] for p in d['plats']], ['Riz sauce arachide'])
        g = d['plats'][0]['groupes']
        self.assertEqual([x['nom'] for x in g], ['Accompagnements', 'Boissons'])
        self.assertEqual(g[0]['options'][1], {'id': 1, 'nom': 'Frites', 'prix': 700})
        self.assertEqual(g[1]['choix'], 'unique')
        self.r.refresh_from_db()
        self.assertEqual(self.r.vues, 1)
        self.client.post(f'{API}{self.r.slug}/clic/')
        self.client.post(f'/restaurants/{self.r.slug}/commander/')
        self.r.refresh_from_db()
        self.assertEqual(self.r.clics_commander, 2)

    def test_site_liste_fiche_et_masque(self):
        self.assertContains(self.client.get('/restaurants/'), 'Chez Test')
        r = self.client.get(f'/restaurants/{self.r.slug}/')
        self.assertContains(r, 'Riz sauce arachide')
        self.assertContains(r, 'Itinéraire')
        self.r.visible = False
        self.r.save()
        self.assertEqual(self.client.get(f'/restaurants/{self.r.slug}/').status_code, 404)
        self.assertContains(self.client.get('/restaurants/'), 'Bientôt des restaurants près de chez vous')

    def test_admin_plat_avec_groupe_d_options(self):
        U = get_user_model()
        self.client.force_login(U.objects.create_superuser(email='a@example.com', password='x-Pass-12345'))
        self.assertEqual(self.client.get(f'/lantanteAdminTech/Restaurants/restaurant/{self.r.pk}/change/').status_code, 200)
        self.assertEqual(self.client.get(f'/lantanteAdminTech/Restaurants/plat/{self.p.pk}/change/').status_code, 200)
        self.assertEqual(self.client.get('/lantanteAdminTech/section/restaurants/').status_code, 200)
