"""Abonnement unique « Accès Épreuves » : fin, renouvellement anticipé, épreuves libres, PDF, achats à l'unité."""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from api_mobile.models import Notification
from concours.models import Contest, ContestCategory, ContestSession, ExamPaper
from Payments import services
from Payments.models import CodePromo, Payment

from .access import can_view_paper, user_can_access
from .annuel import actif, fin_acces
from .models import AccesEpreuves, ReglageAcces

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'
PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'


@override_settings(STORAGES=STORAGES)
@mock.patch('Payments.fedapay.is_enabled', return_value=True)
@mock.patch('Payments.fedapay.mode', return_value='demo')
class AccesTests(APITestCase):
    def setUp(self):
        self.u = get_user_model().objects.create_user(email='a@example.com', password='x-Pass-12345', first_name='Ama',
                                                      last_name='Koffi', is_verified=True)
        self.client.force_authenticate(self.u)
        ReglageAcces.objects.create(prix=5000, duree_jours=365)
        cat = ContestCategory.objects.get(slug='enseignement')
        self.c = Contest.objects.create(acronym='ENS', name='ENS', category=cat, is_published=True)
        self.c2 = Contest.objects.create(acronym='IAI', name='IAI', category=cat, is_published=True)
        s = ContestSession.objects.create(contest=self.c, year=2025)
        self.libre = ExamPaper.objects.create(session=s, title='Maths', is_free=True)
        self.payante = ExamPaper.objects.create(session=s, title='Physique')
        for p in (self.libre, self.payante):
            p.file.save('e.pdf', ContentFile(PDF))

    def _abonner(self, **extra):
        d = {'type': 'acces', 'pays': 'tg', 'operateur': 'togocel', 'telephone': '90000000'}
        d.update(extra)
        r = self.client.post(API + 'paiements/', d, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        p = Payment.objects.get(reference=r.json()['reference'])
        services.mark_paid(p)
        services.mark_paid(p)  # 2e confirmation : rien de plus
        return p

    def test_abonnement_donne_tout_et_une_seule_periode_par_paiement(self, *_):
        self.assertFalse(user_can_access(self.u, self.c))
        p = self._abonner()
        self.assertEqual(p.amount, 5000)
        self.assertEqual(AccesEpreuves.objects.filter(user=self.u).count(), 1)
        self.assertTrue(user_can_access(self.u, self.c) and user_can_access(self.u, self.c2))
        d = self.client.get(API + 'abonnement/').json()
        self.assertTrue(d['actif'])
        self.assertEqual((d['prix'], d['duree_jours']), (5000, 365))

    def test_expiration_et_pdf_refuse(self, *_):
        self._abonner()
        url = f"{API}documents/epreuve/{self.payante.pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        plus_tard = timezone.now() + timedelta(days=366)
        self.assertFalse(actif(self.u, plus_tard))
        AccesEpreuves.objects.update(fin=timezone.now() - timedelta(minutes=1))
        self.assertFalse(user_can_access(self.u, self.c))
        self.assertIn(self.client.get(url).status_code, (403, 404))
        self.assertIn(self.client.get(f'/concours/fichier/epreuve/{self.payante.pk}/').status_code, (302, 403, 404))
        self.assertFalse(self.client.get(API + 'abonnement/').json()['actif'])

    def test_renouvellement_anticipe_s_ajoute(self, *_):
        self._abonner()
        fin1 = fin_acces(self.u)
        self._abonner()
        self.assertEqual(AccesEpreuves.objects.filter(user=self.u).count(), 2)
        self.assertAlmostEqual((fin_acces(self.u) - fin1).total_seconds(), 365 * 86400, delta=5)

    def test_epreuve_libre_sans_abonnement_mais_compte_requis(self, *_):
        self.assertTrue(can_view_paper(self.u, self.libre))
        self.assertFalse(can_view_paper(self.u, self.payante))
        self.assertEqual(self.client.get(f"{API}documents/epreuve/{self.libre.pk}/").status_code, 200)
        d = self.client.get(f"{API}concours/{self.c.slug}/annees/{self.libre.session_id}/").json()
        etat = {e['titre']: (e['gratuite'], e['accessible']) for e in d['epreuves']}
        self.assertEqual(etat, {'Maths': (True, True), 'Physique': (False, False)})
        self.client.force_authenticate(None)
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(can_view_paper(AnonymousUser(), self.libre))

    def test_achat_a_l_unite_conserve_et_plus_vendu(self, *_):
        Payment.objects.create(user=self.u, kind='concours', contest=self.c, amount=1000, description='x',
                               first_name='A', last_name='K', phone='', status='approved', mode='live')
        self.assertTrue(user_can_access(self.u, self.c))
        self.assertFalse(user_can_access(self.u, self.c2))
        r = self.client.post(API + 'paiements/', {'type': 'concours', 'id': self.c2.pk, 'pays': 'tg',
                                                  'operateur': 'togocel', 'telephone': '90000000'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_code_promo_abonnement(self, *_):
        CodePromo.objects.create(code='BAC', type='pct', valeur=20, abonnement=True)
        CodePromo.objects.create(code='TOUT', type='pct', valeur=20)  # sans restriction : valable partout
        prod = CodePromo.objects.create(code='SACS', type='pct', valeur=20)
        from Shop.models import Product
        prod.produits.add(Product.objects.create(name='Sac', description='x', price=100, stock=1))
        r = self.client.post(API + 'paiements/devis/', {'type': 'acces', 'code_promo': 'TOUT'}, format='json').json()
        self.assertEqual(r['remise'], 1000)
        r = self.client.post(API + 'paiements/devis/', {'type': 'acces', 'code_promo': 'SACS'}, format='json').json()
        self.assertEqual((r['remise'], bool(r['message_promo'])), (0, True))  # limité à un produit : refusé

    def test_rappels_7j_1j_expiration_une_fois(self, *_):
        a = AccesEpreuves.objects.create(user=self.u, debut=timezone.now() - timedelta(days=360),
                                         fin=timezone.now() + timedelta(days=5))
        call_command('rappels_acces')
        call_command('rappels_acces')
        self.assertEqual(Notification.objects.filter(utilisateur=self.u).count(), 1)
        a.fin = timezone.now() + timedelta(hours=10)
        a.save()
        call_command('rappels_acces')
        a.fin = timezone.now() - timedelta(hours=1)
        a.save()
        call_command('rappels_acces')
        call_command('rappels_acces')
        titres = list(Notification.objects.filter(utilisateur=self.u).order_by('pk').values_list('titre', flat=True))
        self.assertEqual(titres, ['Abonnement : 7 jours restants', 'Abonnement : dernier jour', 'Abonnement expiré'])

    def test_staff_toujours(self, *_):
        self.u.is_staff = True
        self.u.save()
        self.assertTrue(can_view_paper(self.u, self.payante))
