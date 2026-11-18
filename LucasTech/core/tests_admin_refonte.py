import os
import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
A = '/lantanteAdminTech/'


@override_settings(STORAGES=STORAGES, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class DeuxFacteursTests(TestCase):
    def setUp(self):
        cache.clear()
        self.u = get_user_model().objects.create_superuser(email='admin@x.tg', password='Mot-de-passe-1')

    def _code(self):
        return re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)

    def test_sans_interrupteur_connexion_directe(self):
        with mock.patch.dict(os.environ, {'ADMIN_2FA': ''}):
            r = self.client.post(A + 'login/', {'username': 'admin@x.tg', 'password': 'Mot-de-passe-1'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.client.get(A).status_code, 200)

    def test_code_par_email_essais_et_appareil(self):
        with mock.patch.dict(os.environ, {'ADMIN_2FA': '1'}):
            r = self.client.post(A + 'login/', {'username': 'admin@x.tg', 'password': 'Mot-de-passe-1'})
            self.assertRedirects(r, A + 'verification/', fetch_redirect_response=False)
            self.assertNotEqual(self.client.get(A).status_code, 200)  # pas encore connecté
            code = self._code()
            r = self.client.post(A + 'verification/', {'code': '000000' if code != '000000' else '111111'})
            self.assertContains(r, 'Code incorrect')
            r = self.client.post(A + 'verification/', {'code': code, 'retenir': '1'})
            self.assertEqual(r.status_code, 302)
            self.assertIn('lt_appareil', r.cookies)
            self.assertEqual(self.client.get(A).status_code, 200)
            # appareil retenu : plus de code à la prochaine connexion
            jeton = r.cookies['lt_appareil'].value
            self.client.logout()  # (le client de test vide aussi ses cookies : on remet celui de l'appareil)
            self.client.cookies['lt_appareil'] = jeton
            n = len(mail.outbox)
            r = self.client.post(A + 'login/', {'username': 'admin@x.tg', 'password': 'Mot-de-passe-1'})
            self.assertEqual((r.status_code, len(mail.outbox)), (302, n))
            self.assertNotEqual(r['Location'], A + 'verification/')

    def test_cinq_essais_puis_bloque_et_secours(self):
        from django.core.management import call_command
        with mock.patch.dict(os.environ, {'ADMIN_2FA': '1'}):
            self.client.post(A + 'login/', {'username': 'admin@x.tg', 'password': 'Mot-de-passe-1'})
            code = self._code()
            faux = '000000' if code != '000000' else '111111'
            for _ in range(5):
                r = self.client.post(A + 'verification/', {'code': faux})
            r = self.client.post(A + 'verification/', {'code': code})
            self.assertContains(r, 'Demandez un nouveau code')
            call_command('deux_facteurs', 'desactiver', 'admin@x.tg')
            self.client.logout()
            r = self.client.post(A + 'login/', {'username': 'admin@x.tg', 'password': 'Mot-de-passe-1'})
            self.assertEqual(r.status_code, 302)
            self.assertNotEqual(r['Location'], A + 'verification/')

    def test_code_jamais_dans_les_journaux(self):
        with mock.patch.dict(os.environ, {'ADMIN_2FA': '1'}), self.assertLogs('lantante.2fa', 'INFO') as logs:
            self.client.post(A + 'login/', {'username': 'admin@x.tg', 'password': 'Mot-de-passe-1'})
        self.assertNotIn(self._code(), ' '.join(logs.output))


@override_settings(STORAGES=STORAGES)
class RubriquesAdminTests(TestCase):
    def setUp(self):
        cache.clear()
        self.u = get_user_model().objects.create_superuser(email='admin@x.tg', password='x')
        self.client.force_login(self.u)

    def test_barre_laterale_grands_titres_et_tout_accessible(self):
        from django.contrib import admin
        from core.rubriques import RUBRIQUES, modeles
        r = self.client.get(A)
        self.assertContains(r, 'lt-nav')
        for titre in ('Paiements', 'Boutique', 'Hôtels', 'Location', 'Réglages'):
            self.assertContains(r, titre)
        self.assertNotContains(r, '>Core<')
        tous = {lab for code in RUBRIQUES for lab, _ in modeles(code)}
        for m in admin.site._registry:
            self.assertIn(f'{m._meta.app_label}.{m.__name__}', tous)
        for code in RUBRIQUES:
            self.assertEqual(self.client.get(f'{A}section/{code}/').status_code, 200, code)

    def test_evenements_onglets_et_tableau(self):
        from Events.models import Event
        img = SimpleUploadedFile('c.jpg', b'x', content_type='image/jpeg')
        e = Event.objects.create(title='Concert', description='x', cover=img, starts_at=timezone.now() + timedelta(days=3))
        r = self.client.get(A + 'section/evenements/')
        self.assertContains(r, 'À venir · 1')
        self.assertContains(r, 'Concert')
        r = self.client.get(f'{A}section/evenements/{e.pk}/')
        self.assertContains(r, 'Encaissé')
        self.assertContains(r, 'Exporter')
        csv = self.client.get(f'{A}section/evenements/{e.pk}/export/')
        self.assertEqual(csv['Content-Type'], 'text/csv; charset=utf-8')


@override_settings(STORAGES=STORAGES)
class FicheHotelTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client.force_login(get_user_model().objects.create_superuser(email='admin@x.tg', password='x'))
        from Hotels.models import Hotel
        self.h = Hotel.objects.create(nom='Hôtel Test', ville='Lomé', equipements=['wifi'])

    def test_liste_fiche_ajout_et_retour(self):
        from Hotels.models import Chambre
        fiche = f'{A}section/hotels/{self.h.pk}/'
        self.assertContains(self.client.get(A + 'section/hotels/'), fiche)
        self.assertContains(self.client.get(A + 'Hotels/hotel/'), fiche)
        r = self.client.get(fiche)
        self.assertContains(r, "Modifier l'hôtel")
        self.assertContains(r, 'Aucune chambre')
        ajout = f'{A}Hotels/chambre/add/?hotel={self.h.pk}&retour={fiche}'
        self.assertContains(self.client.get(ajout), f'<option value="{self.h.pk}" selected')
        r = self.client.post(ajout, {'hotel': self.h.pk, 'nom': 'Suite', 'prix_nuit': 50000, 'capacite': 2,
                                     'actif': 'on', 'ordre': 0, '_save': '1',
                                     'photos-TOTAL_FORMS': 0, 'photos-INITIAL_FORMS': 0})
        self.assertRedirects(r, fiche, fetch_redirect_response=False)
        c = Chambre.objects.get(nom='Suite')
        self.assertContains(self.client.get(fiche), '50 000 CFA')
        # sans retour explicite : on revient quand même sur la fiche
        r = self.client.post(f'{A}Hotels/hotel/{self.h.pk}/change/', {
            'nom': 'Hôtel Test', 'ville': 'Lomé', 'actif': 'on', 'ordre': 0, 'etoiles': 3, '_save': '1',
            'photos-TOTAL_FORMS': 0, 'photos-INITIAL_FORMS': 0})
        self.assertRedirects(r, fiche, fetch_redirect_response=False)
        # retour externe refusé
        r = self.client.post(f'{A}Hotels/chambre/{c.pk}/delete/?retour=https://mal.example/', {'post': 'yes'})
        self.assertNotIn('mal.example', r['Location'])
