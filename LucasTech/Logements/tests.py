import tempfile

from django.test import TestCase, override_settings

from core.models import SiteSettings

from .models import Logement

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/logements/'


@override_settings(STORAGES=STORAGES, MEDIA_ROOT=tempfile.mkdtemp())
class LogementsTests(TestCase):
    def setUp(self):
        s = SiteSettings.load()
        s.whatsapp_1 = '+228 92 96 77 87'
        s.save()
        self.a = Logement.objects.create(type='chambre_salon', ville='Lomé', quartier='Adidogomé', loyer=35000,
                                         meuble=False, proprietaire_telephone='+228 90 00 00 01', alias='Adido')
        self.b = Logement.objects.create(type='appartement', ville='Lomé', quartier='Bè Kpota', loyer=150000, meuble=True,
                                         pieces=3, equipements=['clim', 'x'])
        self.c = Logement.objects.create(type='studio', ville='Kara', quartier='Tchaloudè', loyer=40000)
        Logement.objects.create(type='maison', ville='Lomé', quartier='Agoè', loyer=90000, loue=True)

    def _noms(self, **g):
        return {r['quartier'] for r in self.client.get(API, g).json()['resultats']}

    def test_recherche_accents_casse_fautes_partiel(self):
        for q in ('adidogome', 'ADIDOGOMÉ', 'adido', 'adidogme', 'Adidogomé Lomé'):
            self.assertIn('Adidogomé', self._noms(q=q), q)
        self.assertEqual(self._noms(q='be kpota'), {'Bè Kpota'})
        self.assertIn('Adidogomé', self._noms(q='chambre salon'))  # type en clair
        self.assertEqual(self._noms(q='kara'), {'Tchaloudè'})

    def test_filtres_et_loues_masques(self):
        self.assertEqual(self._noms(), {'Adidogomé', 'Bè Kpota', 'Tchaloudè'})  # Agoè : loué
        self.assertEqual(self._noms(ville='Kara'), {'Tchaloudè'})
        self.assertEqual(self._noms(type='appartement'), {'Bè Kpota'})
        self.assertEqual(self._noms(prix_max='50000'), {'Adidogomé', 'Tchaloudè'})
        self.assertEqual(self._noms(meuble='1'), {'Bè Kpota'})
        r = self.client.get(API).json()
        self.assertEqual(r['villes'], ['Kara', 'Lomé'])
        self.assertEqual({t['code'] for t in r['types']}, {'chambre_salon', 'appartement', 'studio'})

    def test_fiche_contact_lantante_proprietaire_prive(self):
        d = self.client.get(f'{API}{self.a.pk}/').json()
        self.assertEqual(d['whatsapp'], '22892967787')
        self.assertIn('Quartier : Adidogomé (Lomé)', d['message_whatsapp'])
        self.assertIn('Loyer : 35 000 CFA par mois', d['message_whatsapp'])
        self.assertNotIn('90 00 00 01', str(d))
        self.assertIn('destination=', d['itineraire'])
        self.assertEqual([e['code'] for e in self.client.get(f'{API}{self.b.pk}/').json()['equipements']], ['clim'])
        loue = Logement.objects.get(quartier='Agoè')
        self.assertEqual(self.client.get(f'{API}{loue.pk}/').status_code, 404)
        self.client.post(f'{API}{self.a.pk}/clic/')
        self.a.refresh_from_db()
        self.assertEqual((self.a.vues, self.a.contacts), (1, 1))

    def test_site(self):
        p = self.client.get('/logements/?q=adidogome')
        self.assertContains(p, 'Adidogomé')
        self.assertNotContains(p, 'Bè Kpota')
        fiche = self.client.get(f'/logements/{self.a.pk}/')
        self.assertContains(fiche, 'wa.me/22892967787')
        self.assertNotContains(fiche, '90 00 00 01')
        Logement.objects.update(loue=True)
        self.assertContains(self.client.get('/logements/'), 'Bientôt disponible')
