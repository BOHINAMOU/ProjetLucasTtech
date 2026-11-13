"""Recherche des concours : catégories, nom complet, sigle, accents, mots partiels et ordre libre."""
from django.test import TestCase, override_settings

from .models import Contest, ContestCategory

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


@override_settings(STORAGES=STORAGES)
class RechercheConcoursTests(TestCase):
    def setUp(self):
        ens = ContestCategory.objects.get_or_create(name='Enseignement', defaults={'slug': 'enseignement'})[0]
        sante = ContestCategory.objects.get_or_create(name='Santé', defaults={'slug': 'sante'})[0]
        adm = ContestCategory.objects.get_or_create(name='Administration', defaults={'slug': 'administration'})[0]
        Contest.objects.create(acronym='ENS', name='École normale supérieure', category=ens, is_published=True)
        Contest.objects.create(acronym='ENI', name="École normale d'instituteurs", category=ens, is_published=True)
        Contest.objects.create(acronym='EAM', name='École des assistants médicaux', category=sante, is_published=True,
                               description='Infirmiers et sages-femmes')
        Contest.objects.create(acronym='ENA', name="École nationale d'administration", category=adm, is_published=True)

    def sigles(self, q):
        r = self.client.get('/api/mobile/v1/concours/', {'q': q})
        self.assertEqual(r.status_code, 200)
        return [c['sigle'] for c in r.json()]

    def test_categorie_sans_accent(self):
        self.assertEqual(self.sigles('santé'), ['EAM'])
        self.assertEqual(self.sigles('sante'), ['EAM'])
        self.assertEqual(set(self.sigles('enseignement')), {'ENS', 'ENI'})

    def test_nom_complet_et_partiel(self):
        self.assertEqual(self.sigles('école normale supérieure')[0], 'ENS')
        self.assertEqual(self.sigles('ecole normale superieure'), ['ENS'])
        self.assertEqual(set(self.sigles('ecole normale')), {'ENS', 'ENI'})
        self.assertEqual(self.sigles('superieure normale'), ['ENS'])  # ordre libre
        self.assertEqual(self.sigles('norm sup'), ['ENS'])  # mots partiels

    def test_sigle_exact_en_premier(self):
        self.assertEqual(self.sigles('ENS')[0], 'ENS')
        self.assertEqual(self.sigles('ens')[0], 'ENS')
        self.assertEqual(self.sigles('ena'), ['ENA'])

    def test_description_et_page_web(self):
        self.assertEqual(self.sigles('infirmiers'), ['EAM'])
        r = self.client.get('/concours/', {'q': 'sante'})
        self.assertEqual([c.acronym for c in r.context['contests']], ['EAM'])
