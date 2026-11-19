import tempfile

from django.test import TestCase, override_settings

from Offres.models import OffreEmploi
from Repetiteurs.models import Repetiteur
from Restaurants.models import Plat, Restaurant

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


@override_settings(STORAGES=STORAGES, MEDIA_ROOT=tempfile.mkdtemp())
class RechercheGeneraleV3Tests(TestCase):
    def setUp(self):
        Repetiteur.objects.create(nom='Mathématiques — 3e', matieres='Mathématiques', niveaux='3e', ville='Lomé',
                                  quartier='Agoè', est_service_lantante=True)
        r = Restaurant.objects.create(nom='Chez Ama', quartier='Bè')
        Plat.objects.create(restaurant=r, nom='Riz sauce arachide', prix=1500)
        OffreEmploi.objects.create(titre='Comptable', entreprise='SOTRA', ville='Kara', description='Poste')

    def _types(self, q, v='3'):
        d = self.client.get('/api/mobile/v1/recherche/', {'q': q, 'v': v}).json()
        return {g['type']: [x['titre'] for x in g['resultats']] for g in d['groupes']}

    def test_trouve_repetiteurs_restaurants_plats_emplois(self):
        self.assertIn('repetiteur', self._types('maths'))
        self.assertIn('repetiteur', self._types('agoe'))
        self.assertEqual(self._types('chez ama')['restaurant'], ['Chez Ama'])
        self.assertEqual(self._types('riz arachide')['restaurant'], ['Riz sauce arachide · Chez Ama'])
        self.assertIn('emploi', self._types('comptable'))
        self.assertNotIn('restaurant', self._types('chez ama', v='2'))  # anciennes versions de l'appli
