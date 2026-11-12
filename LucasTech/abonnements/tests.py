"""Règles clés des abonnements cumulables aux concours."""
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from concours.models import Contest, ContestCategory, ContestSession, ExamPaper
from Payments import services as pay_services
from Payments.models import Payment

from . import services
from .access import accessible_contest_ids, can_view_paper, user_can_access
from .models import ExtensionOption, SubscriptionPlan, UserSubscription

TMP = tempfile.mkdtemp()
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


@override_settings(PRIVATE_MEDIA_ROOT=TMP, MEDIA_ROOT=TMP, STORAGES=STORAGES, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SubscriptionRulesTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._field = ExamPaper._meta.get_field('file')
        cls._storage = cls._field.storage
        cls._field.storage = FileSystemStorage(location=TMP)  # pas de fichiers de test dans private_media

    @classmethod
    def tearDownClass(cls):
        cls._field.storage = cls._storage
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        self.user = get_user_model().objects.create_user(email='eleve@example.com', password='x-Pass-12345')
        self.standard = SubscriptionPlan.objects.get(code='standard')
        self.premium = SubscriptionPlan.objects.get(code='premium')
        self.ultimate = SubscriptionPlan.objects.get(code='ultimate')
        cat = ContestCategory.objects.get(slug='enseignement')
        self.contests = [Contest.objects.create(acronym=f'C{i}', name=f'Concours {i}', category=cat,
                                                is_published=True) for i in range(12)]
        self.ens = Contest.objects.create(acronym='ENS', name='École normale supérieure', category=cat,
                                          is_published=True)

    # ── outils ──
    def _active(self, plan, period='mois'):
        sub = services.create_pending_subscription(self.user, plan, period)
        return services.activate_subscription(sub.pk)

    def _paper(self, contest, free):
        session, _ = ContestSession.objects.get_or_create(contest=contest, year=2024)
        p = ExamPaper(session=session, title='Maths', is_free=free)
        p.file.save('sujet.pdf', ContentFile(b'%PDF-1.4 test'), save=True)
        return p

    # ── règles ──
    def test_standard_un_concours_laisse_deux_places(self):
        sub = self._active(self.standard)
        services.add_contests(sub, self.contests[:1])
        sub.refresh_from_db()
        self.assertEqual(sub.free_slots, 2)

    def test_quatrieme_concours_refuse_avec_standard(self):
        sub = self._active(self.standard)
        services.add_contests(sub, self.contests[:3])
        with self.assertRaises(services.SelectionError):
            services.add_contests(sub, self.contests[3:4])
        self.assertFalse(user_can_access(self.user, self.contests[3]))

    def test_quatre_concours_d_un_coup_refuse(self):
        sub = self._active(self.standard)
        with self.assertRaises(services.SelectionError):
            services.add_contests(sub, self.contests[:4])
        self.assertEqual(sub.contests.count(), 0)

    def test_deux_standards_donnent_six_concours(self):
        s1, s2 = self._active(self.standard), self._active(self.standard)
        services.add_contests(s1, self.contests[:3])
        services.add_contests(s2, self.contests[3:6])
        self.assertEqual(len(accessible_contest_ids(self.user)), 6)
        with self.assertRaises(services.SelectionError):
            services.add_contests(s2, self.contests[6:7])

    def test_standard_plus_premium_onze_concours(self):
        s1, s2 = self._active(self.standard), self._active(self.premium)
        services.add_contests(s1, self.contests[:3])
        services.add_contests(s2, self.contests[3:11])
        self.assertEqual(len(accessible_contest_ids(self.user)), 11)
        self.assertTrue(all(user_can_access(self.user, c) for c in self.contests[:11]))

    def test_expiration_du_premier_standard_laisse_le_second(self):
        s1, s2 = self._active(self.standard), self._active(self.standard)
        services.add_contests(s1, self.contests[:3])
        services.add_contests(s2, self.contests[3:6])
        UserSubscription.objects.filter(pk=s1.pk).update(end_at=timezone.now() - timedelta(minutes=1))
        self.assertFalse(user_can_access(self.user, self.contests[0]))  # coupé à la volée
        self.assertEqual(services.expire_overdue(), 1)
        s1.refresh_from_db()
        s2.refresh_from_db()
        self.assertEqual(s1.status, 'expire')
        self.assertTrue(s2.is_active)
        self.assertTrue(user_can_access(self.user, self.contests[4]))

    def test_doublon_signale(self):
        s1, s2 = self._active(self.standard), self._active(self.standard)
        services.add_contests(s1, [self.ens])
        states = dict((c.pk, st) for c, st in services.selection_states(self.user, s2, [self.ens, self.contests[0]]))
        self.assertEqual(states[self.ens.pk], 'deja')
        self.assertEqual(states[self.contests[0].pk], 'libre')
        with self.assertRaisesMessage(services.SelectionError, 'Déjà accessible : ENS'):
            services.add_contests(s2, [self.ens])

    def test_paiement_confirme_deux_fois_une_seule_activation(self):
        pay = Payment.objects.create(kind='abonnement', amount=1000, description='Standard', user=self.user,
                                     first_name='A', last_name='B', phone='22890000000', mode='sandbox')
        sub = services.create_pending_subscription(self.user, self.standard, 'mois', payment=pay)
        pay_services.mark_paid(pay)
        sub.refresh_from_db()
        first_end = sub.end_at
        self.assertEqual(sub.status, 'actif')
        pay_services.mark_paid(pay)          # webhook reçu une 2e fois
        services.fulfill_payment(pay)        # et activation directe rejouée
        services.activate_subscription(sub.pk)
        sub.refresh_from_db()
        self.assertEqual(sub.end_at, first_end)
        self.assertEqual(UserSubscription.objects.filter(user=self.user, status='actif').count(), 1)

    def test_pas_de_droit_avant_paiement(self):
        sub = services.create_pending_subscription(self.user, self.standard, 'mois')
        with self.assertRaises(services.SelectionError):
            services.add_contests(sub, [self.ens])
        self.assertFalse(user_can_access(self.user, self.ens))

    def test_epreuve_gratuite_accessible_sans_abonnement(self):
        free = self._paper(self.ens, free=True)
        paid = self._paper(self.ens, free=False)
        self.assertTrue(can_view_paper(self.user, free))
        self.assertFalse(can_view_paper(self.user, paid))
        anon = self.client
        self.assertEqual(anon.get(reverse('concours:file', args=['sujet', free.pk])).status_code, 200)
        self.assertEqual(anon.get(reverse('concours:file', args=['sujet', paid.pk])).status_code, 403)

    def test_ens_refuse_si_seul_abonnement_ens_expire(self):
        sub_ens = self._active(self.standard)
        services.add_contests(sub_ens, [self.ens])
        other = self._active(self.standard)
        services.add_contests(other, self.contests[:2])
        paid = self._paper(self.ens, free=False)
        self.client.force_login(self.user)
        url = reverse('concours:file', args=['sujet', paid.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        UserSubscription.objects.filter(pk=sub_ens.pk).update(end_at=timezone.now() - timedelta(seconds=1))
        self.assertFalse(user_can_access(self.user, self.ens))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertTrue(user_can_access(self.user, self.contests[0]))

    def test_ultimate_prolonge_au_lieu_de_doubler(self):
        u1 = self._active(self.ultimate)
        end = u1.end_at
        u2 = self._active(self.ultimate)
        u1.refresh_from_db()
        self.assertEqual(u2.status, 'fusionne')
        self.assertEqual(u1.end_at, end + timedelta(days=30))
        self.assertEqual(UserSubscription.objects.filter(user=self.user).active().count(), 1)
        self.assertTrue(user_can_access(self.user, self.ens))

    def test_extension_ajoute_des_places_et_prix_au_prorata(self):
        sub = self._active(self.standard)
        services.add_contests(sub, self.contests[:3])
        opt = ExtensionOption.objects.get(slots=2)
        UserSubscription.objects.filter(pk=sub.pk).update(end_at=timezone.now() + timedelta(days=15))
        sub.refresh_from_db()
        self.assertEqual(services.extension_price(opt, sub), 350)  # 700 F x 15/30
        ext = services.create_pending_extension(sub, opt)
        with self.assertRaises(services.SelectionError):
            services.add_contests(sub, self.contests[3:4])  # extension pas encore payée
        services.activate_extension(ext.pk)
        sub.refresh_from_db()
        services.add_contests(sub, self.contests[3:5])
        self.assertEqual(len(accessible_contest_ids(self.user)), 5)

    def test_conseil_premium_au_deuxieme_standard(self):
        self.assertEqual(services.advice_for(self.user, self.standard), '')
        self._active(self.standard)
        self.assertIn('Premium', services.advice_for(self.user, self.standard))

    def test_pages_publiques(self):
        self.assertEqual(self.client.get(reverse('concours:index')).status_code, 200)
        self.assertEqual(self.client.get(reverse('abonnements:plans')).status_code, 200)
        self.assertEqual(self.client.get(self.ens.get_absolute_url()).status_code, 200)
        ContestSession.objects.create(contest=self.ens, year=2023)
        r = self.client.get(reverse('concours:session', args=[self.ens.slug, 2023]))
        self.assertContains(r, 'Aucune épreuve disponible')

    def test_mon_espace(self):
        sub = self._active(self.standard)
        services.add_contests(sub, [self.ens])
        self.client.force_login(self.user)
        r = self.client.get(reverse('abonnements:space'))
        self.assertContains(r, 'place libre', count=2)
        r = self.client.get(reverse('abonnements:select', args=[sub.pk]))
        self.assertContains(r, 'Choisi')
        r = self.client.post(reverse('abonnements:select', args=[sub.pk]), {'contests': [self.contests[0].pk]})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(sub.contests.count(), 2)

    @override_settings(DEBUG=True, FEDAPAY_SECRET_KEY='')
    def test_achat_complet_en_mode_demo(self):
        """Formulaire -> paiement en attente (aucun droit) -> paiement confirmé -> abonnement actif."""
        self.client.force_login(self.user)
        form = {'first_name': 'Ama', 'last_name': 'K', 'whatsapp': '90000000', 'city': 'Lomé', 'country': 'tg',
                'operator': 'togocel', 'phone': '90000000', 'periode': 'an', 'submission': 'abc'}
        r = self.client.post(reverse('abonnements:subscribe', args=['premium']), form)
        self.assertEqual(r.status_code, 302)
        sub = UserSubscription.objects.get(user=self.user)
        self.assertEqual((sub.status, sub.price_paid, sub.contest_limit, sub.period), ('en_attente', 20000, 8, 'an'))
        self.assertEqual(sub.payment.kind, 'abonnement')
        self.assertFalse(sub.is_active)
        r = self.client.post(reverse('payments:demo', args=[sub.payment.reference]), {'action': 'pay'})
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'actif')
        self.assertEqual((sub.end_at - sub.start_at).days, 365)

    def test_achat_impose_un_compte(self):
        url = reverse('abonnements:subscribe', args=['standard']) + '?periode=mois'
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r['Location'].startswith(reverse('users:register') + '?next='))
        r = self.client.get(reverse('abonnements:plans'))
        self.assertContains(r, 'Créer mon compte')
        self.assertFalse(UserSubscription.objects.exists())

    def test_concours_de_demo_non_selectionnable(self):
        demo = Contest.objects.create(acronym='DEMO-X', name='Démo', category=self.ens.category,
                                      is_published=True, is_demo=True)
        sub = self._active(self.standard)
        with self.assertRaises(services.SelectionError):
            services.add_contests(sub, [demo])

    def test_historique_connexion_obligatoire_et_contenu(self):
        r = self.client.get(reverse('core:history'))
        self.assertEqual(r.status_code, 302)
        pay = Payment.objects.create(kind='abonnement', amount=1000, description='Abonnement concours Standard',
                                     user=self.user, first_name='A', last_name='B', phone='22890000000')
        self.client.force_login(self.user)
        r = self.client.get(reverse('core:history'))
        self.assertContains(r, 'Abonnement concours Standard')
        self.assertContains(r, pay.reference)
        r = self.client.get(reverse('core:history') + '?type=boutique')
        self.assertNotContains(r, 'Abonnement concours Standard')
