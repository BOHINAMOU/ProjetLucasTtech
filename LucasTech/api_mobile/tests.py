"""Tests de l'API mobile : connexion, accès aux documents (refusé / autorisé / hors connexion), historique."""
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import override_settings
from rest_framework.test import APITestCase

from abonnements import services
from abonnements.models import SubscriptionPlan
from concours.models import Contest, ContestCategory, ContestSession, Correction, ExamPaper
from Payments.models import Payment

TMP = tempfile.mkdtemp()
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'


@override_settings(PRIVATE_MEDIA_ROOT=TMP, MEDIA_ROOT=TMP, STORAGES=STORAGES,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ApiMobileTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._saved = []
        for model in (ExamPaper, Correction):
            field = model._meta.get_field('file')
            cls._saved.append((field, field.storage))
            field.storage = FileSystemStorage(location=TMP)

    @classmethod
    def tearDownClass(cls):
        for field, storage in cls._saved:
            field.storage = storage
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user(email='eleve@example.com', password='x-Pass-12345',
                                             first_name='Ama', last_name='Koffi', phone='+22890000000')
        cat = ContestCategory.objects.get(slug='enseignement')
        self.ens = Contest.objects.create(acronym='ENS', name='École normale supérieure', category=cat,
                                          is_published=True)
        self.autre = Contest.objects.create(acronym='ENA', name="École nationale d'administration", category=cat,
                                            is_published=True)
        Contest.objects.create(acronym='CACHE', name='Non publié', category=cat, is_published=False)
        self.session = ContestSession.objects.create(contest=self.ens, year=2024)
        self.paper = self._paper('Mathématiques', free=False)
        self.free = self._paper('Français', free=True)
        self.corr = Correction(paper=self.paper, kind='officiel')
        self.corr.file.save('corrige.pdf', ContentFile(b'%PDF-1.4 corrige'), save=True)

    def _paper(self, title, free):
        p = ExamPaper(session=self.session, title=title, subject=title, is_free=free)
        p.file.save('sujet.pdf', ContentFile(b'%PDF-1.4 sujet'), save=True)
        return p

    def _login(self):
        r = self.client.post(API + 'auth/login/', {'identifiant': 'eleve@example.com', 'password': 'x-Pass-12345'},
                             format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + r.json()['token'])
        return r.json()

    def _subscribe(self, code, contests=()):
        plan = SubscriptionPlan.objects.get(code=code)
        sub = services.activate_subscription(services.create_pending_subscription(self.user, plan, 'mois').pk)
        if contests:
            services.add_contests(sub, contests)
        return sub

    # ── Connexion ──
    def test_login_ok_par_email_et_telephone(self):
        data = self._login()
        self.assertEqual(data['user']['email'], 'eleve@example.com')
        self.assertEqual(data['user']['first_name'], 'Ama')
        r = self.client.post(API + 'auth/login/', {'identifiant': '+22890000000', 'password': 'x-Pass-12345'},
                             format='json')
        self.assertEqual(r.status_code, 200)

    def test_login_refuse_et_limite(self):
        for _ in range(10):
            r = self.client.post(API + 'auth/login/', {'identifiant': 'eleve@example.com', 'password': 'faux'},
                                 format='json')
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.json()['code'], 'identifiants_invalides')
        r = self.client.post(API + 'auth/login/', {'identifiant': 'eleve@example.com', 'password': 'x-Pass-12345'},
                             format='json')
        self.assertEqual(r.status_code, 429)

    def test_register_me_logout(self):
        r = self.client.post(API + 'auth/register/', {
            'first_name': 'Kodjo', 'last_name': 'Mensah', 'email': 'kodjo@example.com', 'phone': '+22891000000',
            'country': 'Togo', 'password': 'Un-Mot2Passe-solide'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + r.json()['token'])
        me = self.client.get(API + 'me/').json()
        self.assertEqual(me['country'], 'Togo')
        self.assertEqual(me['stats']['abonnements_actifs'], 0)
        self.assertEqual(self.client.post(API + 'auth/logout/').status_code, 200)
        self.assertEqual(self.client.get(API + 'me/').status_code, 401)

    def test_register_email_deja_utilise(self):
        r = self.client.post(API + 'auth/register/', {
            'first_name': 'A', 'last_name': 'B', 'email': 'eleve@example.com', 'phone': '1',
            'password': 'Un-Mot2Passe-solide'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('email', r.json()['errors'])

    def test_password_reset_toujours_200(self):
        from django.core import mail
        self.assertEqual(self.client.post(API + 'auth/password-reset/', {'email': 'inconnu@example.com'},
                                          format='json').status_code, 200)
        self.assertEqual(self.client.post(API + 'auth/password-reset/', {'email': 'eleve@example.com'},
                                          format='json').status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    # ── Catalogue ──
    def test_liste_concours_publies_seulement(self):
        r = self.client.get(API + 'concours/')
        self.assertEqual(r.status_code, 200)
        sigles = {c['sigle'] for c in r.json()}
        self.assertEqual(sigles, {'ENS', 'ENA'})
        ens = next(c for c in r.json() if c['sigle'] == 'ENS')
        self.assertEqual((ens['nb_annees'], ens['nb_epreuves'], ens['accessible']), (1, 2, False))
        self.assertEqual(len(self.client.get(API + 'concours/', {'q': 'normale'}).json()), 1)

    # ── Documents ──
    def test_document_refuse_sans_abonnement(self):
        self._login()
        r = self.client.get(f'{API}documents/epreuve/{self.paper.pk}/')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['code'], 'abonnement_requis')
        r = self.client.get(f'{API}documents/corrige/{self.corr.pk}/')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get(f'{API}documents/epreuve/999999/').json()['code'], 'indisponible')

    def test_document_gratuit_autorise(self):
        r = self.client.get(f'{API}documents/epreuve/{self.free.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b''.join(r.streaming_content), b'%PDF-1.4 sujet')
        self.assertEqual(r['X-Hors-Ligne-Autorise'], '1')
        self.assertIn('no-store', r['Cache-Control'])

    def test_document_autorise_standard_sans_hors_ligne(self):
        self._subscribe('standard', [self.ens])
        self._login()
        r = self.client.get(f'{API}documents/epreuve/{self.paper.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['X-Hors-Ligne-Autorise'], '0')
        self.assertEqual(r['X-Filigrane'], 'eleve@example.com')
        self.assertFalse(r.has_header('X-Hors-Ligne-Jusqu-A'))
        # un autre concours reste fermé
        r = self.client.get(f'{API}concours/{self.ens.slug}/annees/{self.session.pk}/').json()
        maths = next(e for e in r['epreuves'] if e['id'] == self.paper.pk)
        self.assertTrue(maths['accessible'])
        self.assertFalse(maths['hors_ligne_autorise'])

    def test_document_premium_hors_ligne(self):
        sub = self._subscribe('premium', [self.ens])
        self._login()
        r = self.client.get(f'{API}documents/corrige/{self.corr.pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['X-Hors-Ligne-Autorise'], '1')
        self.assertTrue(r['X-Hors-Ligne-Jusqu-A'].startswith(sub.end_at.date().isoformat()[:7]))
        abos = self.client.get(API + 'abonnements/').json()
        self.assertEqual(abos[0]['formule']['code'], 'premium')
        self.assertEqual(abos[0]['places_utilisees'], 1)
        self.assertEqual(abos[0]['concours'], [{'sigle': 'ENS', 'nom': 'École normale supérieure'}])

    # ── Historique ──
    def test_historique(self):
        Payment.objects.create(kind='abonnement', status='approved', amount=2000, description='Abonnement Standard',
                               user=self.user, first_name='Ama', last_name='Koffi', phone='90000000')
        Payment.objects.create(kind='service', status='pending', amount=5000, description='Création de site',
                               user=self.user, first_name='Ama', last_name='Koffi', phone='90000000')
        other = get_user_model().objects.create_user(email='autre@example.com', password='x-Pass-12345')
        Payment.objects.create(kind='service', status='approved', amount=1, description='Pas à moi', user=other,
                               first_name='B', last_name='C', phone='1')
        self.assertEqual(self.client.get(API + 'historique/').status_code, 401)
        self._login()
        rows = self.client.get(API + 'historique/').json()
        self.assertEqual([r['titre'] for r in rows], ['Création de site', 'Abonnement Standard'])
        self.assertEqual(rows[0]['devise'], 'FCFA')
        self.assertEqual(rows[0]['statut'], 'en_attente')
        concours = self.client.get(API + 'historique/', {'type': 'concours'}).json()
        self.assertEqual(len(concours), 1)
        self.assertEqual(concours[0]['type'], 'concours')
        self.assertEqual(len(self.client.get(API + 'historique/', {'type': 'paiements'}).json()), 2)

    # ── Suppression du compte ──
    def test_suppression_compte(self):
        self._login()
        r = self.client.delete(API + 'me/', {'password': 'mauvais'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'mot_de_passe_incorrect')
        r = self.client.delete(API + 'me/', {'password': 'x-Pass-12345'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['resultat'], 'supprime')
        self.assertFalse(get_user_model().objects.filter(email='eleve@example.com').exists())
        self.assertEqual(self.client.get(API + 'me/').status_code, 401)

    def test_suppression_compte_avec_achats_anonymise(self):
        pay = Payment.objects.create(kind='service', status='approved', amount=5000, description='Site',
                                     user=self.user, first_name='Ama', last_name='Koffi', phone='9')
        self._login()
        r = self.client.delete(API + 'me/', {'password': 'x-Pass-12345'}, format='json')
        self.assertEqual(r.json()['resultat'], 'anonymise')
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(self.user.has_usable_password())
        self.assertNotIn('eleve', self.user.email)
        self.assertEqual(self.user.first_name, '')
        pay.refresh_from_db()
        self.assertEqual(pay.user_id, self.user.pk)
        self.client.credentials()
        r = self.client.post(API + 'auth/login/', {'identifiant': 'eleve@example.com', 'password': 'x-Pass-12345'},
                             format='json')
        self.assertEqual(r.status_code, 400)
