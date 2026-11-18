import tempfile

from django.test import TestCase, override_settings

from core.models import SiteSettings

from .models import Chambre, Hotel

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


@override_settings(STORAGES=STORAGES, MEDIA_ROOT=tempfile.mkdtemp())
class HotelsTests(TestCase):
    def setUp(self):
        s = SiteSettings.load()
        s.whatsapp_1 = '+228 92 96 77 87'
        s.save()
        self.h = Hotel.objects.create(nom='Hôtel Océan', ville='Lomé', quartier='Bè', equipements=['wifi', 'piscine', 'x'])
        self.c = Chambre.objects.create(hotel=self.h, nom='Chambre double', prix_nuit=25000, capacite=2)
        Hotel.objects.create(nom='Hôtel Kara', ville='Kara')
        Hotel.objects.create(nom='Caché', ville='Lomé', actif=False)

    def test_liste_recherche_villes(self):
        r = self.client.get('/api/mobile/v1/hotels/').json()
        self.assertEqual({h['nom'] for h in r['resultats']}, {'Hôtel Océan', 'Hôtel Kara'})
        self.assertEqual(r['villes'], ['Kara', 'Lomé'])
        r = self.client.get('/api/mobile/v1/hotels/?q=ocean').json()  # sans accent ni majuscule
        self.assertEqual([h['nom'] for h in r['resultats']], ['Hôtel Océan'])
        self.assertEqual(r['resultats'][0]['a_partir_de'], 25000)
        r = self.client.get('/api/mobile/v1/hotels/?q=be').json()  # quartier
        self.assertIn('Hôtel Océan', [h['nom'] for h in r['resultats']])
        r = self.client.get('/api/mobile/v1/hotels/?ville=Kara').json()
        self.assertEqual([h['nom'] for h in r['resultats']], ['Hôtel Kara'])

    def test_fiche_chambre_et_contact_par_defaut(self):
        d = self.client.get(f'/api/mobile/v1/hotels/{self.h.slug}/').json()
        self.assertEqual([e['code'] for e in d['equipements']], ['wifi', 'piscine'])
        self.assertEqual(d['whatsapp'], '22892967787')  # pas de WhatsApp de l'hôtel : notre numéro
        self.assertEqual(d['chambres'][0]['nom'], 'Chambre double')
        c = self.client.get(f'/api/mobile/v1/hotels/chambres/{self.c.pk}/').json()
        self.assertIn('Chambre double — Hôtel Océan', c['message_whatsapp'])
        self.assertIn('/hotels/', c['message_whatsapp'])
        self.h.refresh_from_db()
        self.h.whatsapp = '90112233'
        self.h.save()
        self.assertEqual(self.client.get(f'/api/mobile/v1/hotels/{self.h.slug}/').json()['whatsapp'], '22890112233')
        self.client.post(f'/api/mobile/v1/hotels/{self.h.slug}/clic/reserver/')
        self.h.refresh_from_db()
        self.assertEqual((self.h.vues, self.h.clics_reserver), (2, 1))
        self.assertEqual(self.client.get('/api/mobile/v1/hotels/cache/').status_code, 404)

    def test_site(self):
        self.assertContains(self.client.get('/hotels/'), 'Hôtel Océan')
        p = self.client.get(f'/hotels/{self.h.slug}/')
        self.assertContains(p, 'Chambre double')
        self.assertContains(p, 'wa.me/22892967787')
        Hotel.objects.update(actif=False)
        self.assertContains(self.client.get('/hotels/'), 'Bientôt disponible')
