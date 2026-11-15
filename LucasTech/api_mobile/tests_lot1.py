"""Lot 1 (1.6.0) : événements sans date ni lieu, carrousel choisi, recherche globale, notifications,
actualités lues, et achat unique d'un concours (accès à vie)."""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'


@override_settings(STORAGES=STORAGES)
class Lot1Tests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email='l@example.com', password='x-Pass-12345',
                                                         first_name='Ama', last_name='Koffi', is_verified=True)

    def test_evenement_sans_date_ni_lieu(self):
        from Events.models import Event
        e = Event.objects.create(title='Aide aux orphelins', description='Aide.', kind='soutien')
        self.assertFalse(e.is_past)
        d = self.client.get(API + 'evenements/').json()
        titres = [x['titre'] for x in (d['resultats'] if isinstance(d, dict) else d)]
        self.assertIn('Aide aux orphelins', titres)
        f = self.client.get(f'{API}evenements/{e.pk}/').json()
        self.assertEqual((f['date'], f['lieu']), (None, ''))
        r = self.client.get(e.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'fa-location-dot')

    def test_carrousel_choisi_par_l_admin(self):
        from Publications.models import Publication
        from api_mobile.models import CarouselItem
        p = Publication.objects.create(author=self.user, title='Rentrée 2027', content='x', is_published=True,
                                       cover_image='publications/covers/a.jpg')
        CarouselItem.objects.create(cible='publication', cible_id=p.pk, ordre=1)
        CarouselItem.objects.create(cible='publication', cible_id=p.pk, actif=False)
        CarouselItem.objects.create(cible='publication', cible_id=p.pk, fin=timezone.now() - timedelta(days=1))
        d = self.client.get(API + 'carrousel/').json()
        self.assertEqual([(x['type'], x['id'], x['titre']) for x in d], [('publication', p.pk, 'Rentrée 2027')])

    def test_recherche_globale(self):
        from Shop.models import Product
        Product.objects.create(name='Clé USB 64 Go', price=5000, stock=3)
        d = self.client.get(API + 'recherche/?q=usb').json()
        self.assertEqual(d['groupes'][0]['type'], 'produit')
        self.assertEqual(self.client.get(API + 'recherche/?q=u').json()['groupes'], [])

    def test_notifications(self):
        from api_mobile.models import Notification
        from api_mobile.notifs import notifier
        autre = get_user_model().objects.create_user(email='o@example.com', password='x-Pass-12345', is_verified=True)
        Notification.objects.create(titre='Bienvenue', message='Nouveautés', audience='tous')
        notifier(self.user, 'Paiement réussi', 'Merci')
        notifier(autre, "Pour quelqu'un d'autre", 'x')
        self.client.force_authenticate(self.user)
        d = self.client.get(API + 'notifications/').json()
        self.assertEqual((d['non_lues'], len(d['resultats'])), (2, 2))
        nid = d['resultats'][0]['id']
        self.assertEqual(self.client.post(f'{API}notifications/{nid}/lue/').json()['non_lues'], 1)
        d = self.client.get(API + 'notifications/').json()
        self.assertNotIn(nid, [n['id'] for n in d['resultats']])  # lue = retirée de la liste
        self.assertEqual(len(d['resultats']), 1)
        self.assertEqual(self.client.post(API + 'notifications/lues/').json()['non_lues'], 0)
        self.assertEqual(self.client.get(API + 'notifications/').json()['resultats'], [])
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(API + 'notifications/').status_code, 401)

    def test_actualites_lues(self):
        from Publications.models import Publication
        p = Publication.objects.create(author=self.user, title='Article', content='x', is_published=True)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(API + 'publications/lues/').json(), [])
        self.client.post(f'{API}publications/{p.pk}/lu/')
        self.assertEqual(self.client.get(API + 'publications/lues/').json(), [p.pk])


@override_settings(STORAGES=STORAGES)
class AchatConcoursTests(APITestCase):
    def setUp(self):
        from concours.models import Contest, ContestCategory, ContestSession, ExamPaper
        self.user = get_user_model().objects.create_user(email='c@example.com', password='x-Pass-12345',
                                                         first_name='Ama', last_name='Koffi', is_verified=True)
        cat = ContestCategory.objects.get(slug='enseignement')
        self.c = Contest.objects.create(acronym='IAI', name="Institut Africain d'Informatique", category=cat,
                                        is_published=True, access_price=1500)
        self.autre = Contest.objects.create(acronym='ENS', name='École normale', category=cat, is_published=True)
        s = ContestSession.objects.create(contest=self.c, year=2025)
        self.paper = ExamPaper.objects.create(session=s, title='Maths', file='x.pdf')

    def _payer(self):
        from Payments.models import Payment
        return Payment.objects.create(user=self.user, kind='concours', contest=self.c, status='approved',
                                      amount=1500, description='Concours : IAI', first_name='Ama', last_name='Koffi',
                                      phone='+22890000000', paid_at=timezone.now())

    def test_acces_a_vie_au_seul_concours_achete(self):
        from abonnements.access import can_view_paper, user_can_access
        self.assertFalse(user_can_access(self.user, self.c))
        p = self._payer()
        self.assertTrue(user_can_access(self.user, self.c))
        self.assertFalse(user_can_access(self.user, self.autre))
        self.assertTrue(can_view_paper(self.user, self.paper))
        from concours.models import ContestSession, ExamPaper
        futur = ExamPaper.objects.create(session=ContestSession.objects.create(contest=self.c, year=2030),
                                         title='Phy', file='y.pdf')
        self.assertTrue(can_view_paper(self.user, futur))  # années futures comprises
        p.status = 'refunded'
        p.save()
        self.assertFalse(user_can_access(self.user, self.c))  # un remboursement retire l'accès

    def test_api_plus_de_vente_a_l_unite_mais_achat_conserve_hors_ligne(self):
        self.client.force_authenticate(self.user)
        d = next(x for x in self.client.get(API + 'concours/').json() if x['sigle'] == 'IAI')
        self.assertEqual((d['prix_acces'], d['accessible']), (0, False))
        with mock.patch('Payments.fedapay.is_enabled', return_value=True), \
                mock.patch('Payments.fedapay.mode', return_value='demo'):
            r = self.client.post(API + 'paiements/', {'type': 'concours', 'id': self.c.pk, 'pays': 'tg',
                                                      'operateur': 'togocel', 'telephone': '90000000'}, format='json')
        self.assertEqual(r.status_code, 400)  # plus vendu à l'unité
        self._payer()  # ancien achat
        d = next(x for x in self.client.get(API + 'concours/').json() if x['sigle'] == 'IAI')
        self.assertTrue(d['accessible'])
        from api_mobile.utils import Rights
        self.assertTrue(Rights(self.user).offline_allowed(self.paper))

    def test_site_propose_l_abonnement(self):
        r = self.client.get(self.c.get_absolute_url())
        self.assertContains(r, "S'abonner")
        self.assertNotContains(r, 'Débloquer')
        self.assertRedirects(self.client.get(f'/paiement/concours/{self.c.pk}/'), '/paiement/acces/0/',
                             fetch_redirect_response=False)
        self.assertEqual(self.client.get('/paiement/acces/0/').status_code, 302)  # connexion demandée
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/paiement/acces/0/'), 'Accès Épreuves')
        self.assertEqual(self.client.get('/abonnements/').status_code, 302)  # formules plus vendues


class RubriquesServicesTests(APITestCase):
    def test_grandes_categories_et_sous_categories(self):
        from Services.models import Service, ServiceCategory
        num = ServiceCategory.objects.create(name='Services numériques', slug='numeriques', order=0)
        dev = ServiceCategory.objects.create(name='Développement', slug='dev', parent=num)
        vide = ServiceCategory.objects.create(name='Vide', slug='vide')
        admin = get_user_model().objects.create_superuser(email='r@example.com', password='x-Pass-12345')
        Service.objects.create(title='Site web', category=dev, is_active=True, description='x', admin=admin)
        d = self.client.get(API + 'services/rubriques/').json()
        self.assertEqual([r['nom'] for r in d], ['Services numériques'])  # « Vide » n'apparaît pas
        self.assertEqual((d[0]['nb'], d[0]['groupes'][0]['nom']), (1, 'Développement'))
        self.assertEqual(vide.sous_categories.count(), 0)
