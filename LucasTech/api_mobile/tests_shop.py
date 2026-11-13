"""Achats et services DANS l'application (sans ouvrir le site) : paiement Mobile Money, contact, profil,
pages légales, annonces des concours, choix des concours d'un abonnement, téléchargements récupérables."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase

from abonnements import services as abo
from abonnements.models import SubscriptionPlan
from concours.models import Contest, ContestCategory, ContestSession, ExamPaper

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'


@override_settings(STORAGES=STORAGES, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AppliSansSiteTests(APITestCase):
    def setUp(self):
        from Shop.models import Product
        self.user = get_user_model().objects.create_user(email='eleve@example.com', password='x-Pass-12345',
                                                         first_name='Ama', last_name='Koffi', is_verified=True)
        self.client.force_authenticate(self.user)
        self.product = Product.objects.create(name='Annale SVT', price=3000, stock=5)
        cat = ContestCategory.objects.get(slug='enseignement')
        self.ens = Contest.objects.create(acronym='ENS', name='École normale supérieure', category=cat,
                                          is_published=True)

    def test_moyens_de_paiement(self):
        d = self.client.get(API + 'paiements/moyens/').json()
        tg = next(p for p in d['pays'] if p['code'] == 'tg')
        self.assertIn('togocel', [o['code'] for o in tg['operateurs']])

    @mock.patch('Payments.fedapay.is_enabled', return_value=True)
    @mock.patch('Payments.fedapay.mode', return_value='demo')
    def test_paiement_produit_dans_l_appli(self, *_):
        r = self.client.post(API + 'paiements/', {'type': 'produit', 'id': self.product.pk, 'quantite': 2,
                                                  'pays': 'tg', 'operateur': 'togocel', 'telephone': '90 00 00 00',
                                                  'ville': 'Lomé, Bè'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertEqual((d['statut'], d['montant']), ('en_attente', 6000))
        self.assertNotIn('lantantetechnologie.com', d['url_fedapay'])
        s = self.client.get(f"{API}paiements/{d['reference']}/").json()
        self.assertEqual(s['reference'], d['reference'])
        # numéro qui n'est pas de l'opérateur : refus clair
        r = self.client.post(API + 'paiements/', {'type': 'produit', 'id': self.product.pk, 'pays': 'tg',
                                                  'operateur': 'togocel', 'telephone': '96 00 00 00'}, format='json')
        self.assertEqual(r.status_code, 400)

    @mock.patch('Payments.fedapay.is_enabled', return_value=True)
    @mock.patch('Payments.fedapay.mode', return_value='demo')
    def test_paiement_abonnement_libre_choix(self, *_):
        r = self.client.post(API + 'paiements/', {'type': 'abonnement', 'formule': 'ultimate', 'periode': 'an',
                                                  'pays': 'tg', 'operateur': 'moov_tg', 'telephone': '96000000'},
                             format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()['montant'], SubscriptionPlan.objects.get(code='ultimate').yearly_price)

    def test_contact_par_email(self):
        r = self.client.post(API + 'contact/', {'sujet': 'Aide', 'message': 'Je ne trouve pas mon épreuve.'},
                             format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('Je ne trouve pas mon épreuve.', mail.outbox[-1].body)
        self.assertIn('eleve@example.com', mail.outbox[-1].body)
        self.assertIn('email', self.client.get(API + 'contact/').json())

    def test_profil_et_pages(self):
        r = self.client.patch(API + 'me/profil/', {'phone': '+22890000000', 'city': 'Kara'}, format='json')
        self.assertEqual(r.json()['phone'], '+22890000000')
        d = self.client.get(API + 'pages/confidentialite/').json()
        self.assertTrue(d['contenu'])
        self.assertNotIn('<', d['contenu'][:200])

    def test_annonces_concours(self):
        from Publications.models import Publication, PublicationCategory
        cat = PublicationCategory.objects.get(slug='concours')
        Publication.objects.create(author=self.user, title='Concours ENS 2027 : inscriptions ouvertes',
                                   content='<p>Dépôt des dossiers.</p>', is_published=True, category=cat)
        Publication.objects.create(author=self.user, title='Fête de la musique', content='x', is_published=True)
        self.assertEqual([a['titre'] for a in self.client.get(API + 'concours/annonces/').json()],
                         ['Concours ENS 2027 : inscriptions ouvertes'])
        self.assertEqual(len(self.client.get(f'{API}concours/{self.ens.slug}/annonces/').json()), 1)
        art = Publication.objects.create(author=self.user, title='Galerie', is_published=True,
                                         content='<p>Texte</p><img src="/media/publications/a.jpg"><img src="https://x.tg/b.png">')
        d = self.client.get(f'{API}publications/{art.pk}/').json()
        self.assertEqual(len(d['images']), 2)
        self.assertTrue(d['images'][0].endswith('/media/publications/a.jpg'))

    def test_choix_des_concours_dans_l_appli(self):
        sub = abo.activate_subscription(abo.create_pending_subscription(
            self.user, SubscriptionPlan.objects.get(code='standard'), 'mois').pk)
        d = self.client.get(f'{API}abonnements/{sub.pk}/concours/').json()
        self.assertEqual(d['places_libres'], 3)
        d = self.client.post(f'{API}abonnements/{sub.pk}/concours/', {'concours': [self.ens.pk]}, format='json').json()
        self.assertEqual(d['places_libres'], 2)
        self.assertEqual(next(c for c in d['concours'] if c['id'] == self.ens.pk)['etat'], 'ici')

    def test_telechargements_recuperables(self):
        s = ContestSession.objects.create(contest=self.ens, year=2024)
        p = ExamPaper.objects.create(session=s, title='Maths', file='x.pdf')
        self.client.post(API + 'telechargements/', {'type': 'epreuve', 'id': p.pk, 'titre': 'Maths',
                                                    'sous_titre': 'ENS 2024'}, format='json')
        d = self.client.get(API + 'telechargements/').json()
        self.assertEqual((d[0]['titre'], d[0]['accessible']), ('Maths', False))  # plus d'abonnement : pas récupérable

    def test_historique_detail(self):
        from Payments.models import Payment
        p = Payment.objects.create(kind='product', product=self.product, status='canceled', amount=6000,
                                   description='Annale SVT × 2', user=self.user, first_name='Ama', last_name='Koffi',
                                   phone='+22890123456', operator='togocel', failure_reason='Annulé sur le téléphone',
                                   items=[{'product': self.product.pk, 'quantity': 2, 'price': 3000}])
        rows = self.client.get(API + 'historique/').json()
        cle = rows[0]['cle']
        d = self.client.get(f'{API}historique/{cle}/').json()
        self.assertEqual((d['reference'], d['statut'], d['quantite'], d['montant']), (p.reference, 'annule', 2, 6000))
        self.assertEqual(d['telephone'][-4:], '3456')
        self.assertNotIn('90123', d['telephone'])
        self.assertEqual(d['achat'], {'type': 'produit', 'id': self.product.pk, 'quantite': 2})
        other = get_user_model().objects.create_user(email='x@example.com', password='x-Pass-12345', is_verified=True)
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get(f'{API}historique/{cle}/').status_code, 404)

    def test_espace_services(self):
        from Services.models import Service, ServiceCategory
        cat = ServiceCategory.objects.create(name='Web', slug='web')
        Service.objects.create(admin=self.user, title='Site vitrine', description='x', category=cat, price=1000)
        d = self.client.get(API + 'services/espace/').json()
        self.assertEqual(d[0]['nom'], 'Web')
        self.assertEqual(d[0]['services'][0]['titre'], 'Site vitrine')

    def test_actualite_site_ou_appli(self):
        from Publications.models import Publication
        Publication.objects.create(author=self.user, title='Appli seulement', content='x', is_published=True,
                                   show_on_site=False, show_in_app=True)
        Publication.objects.create(author=self.user, title='Site seulement', content='x', is_published=True,
                                   show_on_site=True, show_in_app=False)
        titres = [a['titre'] for a in self.client.get(API + 'publications/').json()]
        self.assertIn('Appli seulement', titres)
        self.assertNotIn('Site seulement', titres)
        r = self.client.get('/actualites/')
        self.assertContains(r, 'Site seulement')
        self.assertNotContains(r, 'Appli seulement')


class TexteEtImagesTests(APITestCase):
    def test_liens_du_texte_conserves(self):
        from api_mobile.catalog import text
        t = text('<p>Voir <a href="https://x.tg/liste.pdf">la liste</a> et <a href="https://x.tg">https://x.tg</a></p>')
        self.assertIn('la liste https://x.tg/liste.pdf', t)
        self.assertEqual(t.count('https://x.tg'), 2)

    def test_image_hors_site_inchangee(self):
        from api_mobile.catalog import grande_url
        self.assertEqual(grande_url(None, 'https://ailleurs.tg/a.jpg'), 'https://ailleurs.tg/a.jpg')
