from django.test import TestCase, override_settings

from Ecoles.images import domaine
from Ecoles.models import Ecole, Filiere


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class ImagesEcolesTests(TestCase):
    def test_aucune_ecole_ni_filiere_sans_image(self):
        e = Ecole.objects.create(nom='École sans photo', type='universite', cycles=['superieur'])
        Filiere.objects.create(ecole=e, nom='Licence Génie civil')
        Filiere.objects.create(ecole=e, nom='Licence Réseaux et télécoms')
        Filiere.objects.create(ecole=e, nom='Filière au nom inconnu')
        Ecole.objects.create(nom='École sans filière', type='lycee', cycles=['lycee'])
        r = self.client.get('/api/mobile/v1/ecoles/').json()
        liste = r['resultats'] if isinstance(r, dict) else r
        self.assertEqual(len(liste), 2)
        for it in liste:
            self.assertTrue(it['couverture'] and it['image_vignette'], it['nom'])
            d = self.client.get(f"/api/mobile/v1/ecoles/{it['slug']}/").json()
            self.assertTrue(d['couverture_grande'], it['nom'])
            for f in d['filieres']:
                self.assertTrue(f['image'], f['nom'])
                self.assertIn('/static/ecoles/domaines/', f['image'])

    def test_domaines(self):
        self.assertEqual(domaine('Licence Génie civil'), 'btp')
        self.assertEqual(domaine('Licence Systèmes et réseaux informatiques'), 'reseaux')
        self.assertEqual(domaine('Licence Génie eau, assainissement'), 'chantier')
        self.assertEqual(domaine('Licence Communication-marketing'), 'medias')
        self.assertEqual(domaine('Quelque chose'), 'defaut')
