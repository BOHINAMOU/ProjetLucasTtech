from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Repetiteur

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'


@override_settings(STORAGES=STORAGES)
class RepetiteursTests(APITestCase):
    def setUp(self):
        Repetiteur.objects.create(nom='Kossi Agbéko', matieres='Mathématiques, Physique-Chimie', ville='Lomé',
                                  quartier='Bè', whatsapp='+228 90 00 00 01', email='k@example.com', telephone='+22890000001',
                                  niveaux='3e, Tle', tarif='15 000 CFA / mois')
        Repetiteur.objects.create(nom='Afi Mensah', matieres='Anglais', ville='Kara')
        Repetiteur.objects.create(nom='Caché', matieres='SVT', ville='Lomé', actif=False)

    def test_liste_recherche_filtres_et_fiche(self):
        d = self.client.get(API + 'repetiteurs/').json()
        self.assertEqual([r['nom'] for r in d['resultats']], ['Afi Mensah', 'Kossi Agbéko'])
        self.assertEqual(d['matieres'], ['Anglais', 'Mathématiques', 'Physique-Chimie'])
        self.assertEqual(d['villes'], ['Kara', 'Lomé'])
        self.assertEqual([r['nom'] for r in self.client.get(API + 'repetiteurs/?q=physique').json()['resultats']],
                         ['Kossi Agbéko'])
        self.assertEqual(len(self.client.get(API + 'repetiteurs/?ville=Kara').json()['resultats']), 1)
        self.assertEqual(len(self.client.get(API + 'repetiteurs/?matiere=Anglais').json()['resultats']), 1)
        k = Repetiteur.objects.get(nom='Kossi Agbéko')
        f = self.client.get(f'{API}repetiteurs/{k.pk}/').json()
        self.assertEqual((f['whatsapp'], f['email'], f['telephone'], f['tarif']),
                         ('22890000001', 'k@example.com', '+22890000001', '15 000 CFA / mois'))
        cache = Repetiteur.objects.get(nom='Caché')
        self.assertEqual(self.client.get(f'{API}repetiteurs/{cache.pk}/').status_code, 404)

    def test_role_delegue(self):
        from core.models import Delegation
        u = get_user_model().objects.create_user(email='rep@example.com', password='x-Pass-12345', is_verified=True)
        Delegation.objects.create(user=u, type='repetiteurs')
        u.refresh_from_db()
        self.assertTrue(u.is_staff and u.has_perm('Repetiteurs.add_repetiteur'))
        self.client.force_login(u)
        self.assertContains(self.client.get('/lantanteAdminTech/Repetiteurs/repetiteur/'), 'Kossi')
