import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from Payments.models import Payment
from Payments.services import mark_paid

from . import candidatures
from .models import Candidature, HistoriqueCandidature, Repetiteur

MEDIA = tempfile.mkdtemp()
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


def _image(nom='photo.png'):
    b = io.BytesIO()
    Image.new('RGB', (40, 40), 'green').save(b, 'PNG')
    return SimpleUploadedFile(nom, b.getvalue(), content_type='image/png')


def _pdf(nom='piece.pdf'):
    return SimpleUploadedFile(nom, b'%PDF-1.4 test', content_type='application/pdf')


@override_settings(MEDIA_ROOT=MEDIA, STORAGES=STORAGES, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CandidatureTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)
        from pathlib import Path
        from django.conf import settings
        for f in Path(settings.PRIVATE_MEDIA_ROOT, 'candidatures', 'pieces').glob('*'):
            if f.name.startswith(('recto', 'verso')):
                f.unlink(missing_ok=True)

    def tearDown(self):
        for c in Candidature.objects.all():
            for f in (c.piece_recto, c.piece_verso):
                if f:
                    f.delete(save=False)

    def setUp(self):
        self.u = None  # sans compte : n'importe qui peut déposer un dossier
        from django.core.cache import cache
        cache.clear()  # limite anti-spam remise à zéro

    def _deposer(self, url='/repetiteurs/devenir/', **extra):
        d = {'prenom': 'Kossi', 'nom': 'Mensah', 'telephone': '90000000', 'whatsapp': '22890000000',
             'email': 'prof@example.com', 'matieres': 'Maths, Physique', 'niveaux': 'Tle', 'ville': 'Lomé',
             'quartier': 'Bè', 'piece_type': 'cni', 'piece_numero': 'A123',
             'photo': _image(), 'piece_recto': _pdf('recto.pdf')}
        d.update(extra)
        return self.client.post(url, d)

    def _payer(self, c):
        p = Payment.objects.create(kind='candidature', amount=2000, description='Candidature', user=self.u,
                                   first_name='Kossi', last_name='Mensah', phone='90000000',
                                   items=[{'candidature': c.pk}])
        mark_paid(p)
        return p

    def test_parcours_complet_puis_validation_cree_la_fiche(self):
        self.assertEqual(self.client.get('/repetiteurs/devenir/').status_code, 200)
        r = self._deposer()
        c = Candidature.objects.get()
        self.assertEqual(c.statut, 'a_payer')
        self.assertIn(f'/candidature/{c.pk}', r['Location'])
        self.assertIsNone(c.user)
        self.assertEqual(c.numero, f'R{c.pk:05d}')
        # la page de paiement s'ouvre sans compte, dans le même navigateur
        self.assertEqual(self.client.get(r['Location']).status_code, 200)
        # un autre navigateur ne peut pas payer ce dossier sans son lien
        from django.test import Client
        self.assertEqual(Client().get(r['Location']).status_code, 404)
        p = self._payer(c)
        mark_paid(p)  # confirmation reçue deux fois : un seul effet
        c.refresh_from_db()
        self.assertEqual(c.statut, 'a_verifier')
        self.assertEqual(HistoriqueCandidature.objects.filter(candidature=c, action="Paiement confirmé").count(), 1)
        rep = candidatures.valider(c, 'admin')
        self.assertTrue(rep.actif)
        self.assertFalse(rep.est_exemple)
        noms = [x['nom'] for x in self.client.get('/api/mobile/v1/repetiteurs/').json()['resultats']]
        self.assertIn('Kossi Mensah', noms)
        self.assertEqual(self.client.get(c.get_absolute_url()).status_code, 200)

    def test_correction_sans_repayer(self):
        self._deposer()
        c = Candidature.objects.get()
        self._payer(c)
        c.refresh_from_db()
        candidatures.demander_correction(c, "Photo floue", 'admin')
        from django.test import Client
        autre = Client()  # le candidat revient plus tard, depuis le lien reçu
        modifier = f'/repetiteurs/dossier/{c.jeton}/modifier/'
        self.assertContains(autre.get(modifier), 'Photo floue')
        self.client = autre
        r = self._deposer(url=modifier, photo=_image('nette.png'))
        self.assertEqual(r['Location'], c.get_absolute_url())
        c.refresh_from_db()
        self.assertEqual(c.statut, 'a_verifier')
        self.assertEqual(Payment.objects.filter(kind='candidature').count(), 1)

    def test_suivi_seulement_avec_le_bon_jeton(self):
        self._deposer()
        c = Candidature.objects.get()
        self.assertEqual(len(c.jeton), 43)
        self.assertContains(self.client.get(c.get_absolute_url()), c.numero)
        self.assertEqual(self.client.get('/repetiteurs/dossier/faux-jeton/').status_code, 404)
        self.assertEqual(self.client.get(f'/repetiteurs/dossier/{c.jeton[:-1]}x/').status_code, 404)

    def test_piege_a_robots_et_retrouver(self):
        r = self._deposer(site_internet='http://spam')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Candidature.objects.exists())
        self._deposer()
        c = Candidature.objects.get()
        r = self.client.post('/repetiteurs/retrouver/', {'numero': c.numero, 'contact': '+228 90 00 00 00'})
        self.assertContains(r, c.get_absolute_url())
        r = self.client.post('/repetiteurs/retrouver/', {'numero': c.numero, 'contact': '91111111'})
        self.assertNotContains(r, c.jeton)

    def test_whatsapp_obligatoire(self):
        self.assertEqual(self._deposer(whatsapp='').status_code, 200)
        self.assertEqual(self._deposer(whatsapp='123').status_code, 200)
        self.assertFalse(Candidature.objects.exists())
        self.assertEqual(self._deposer(whatsapp='kkkkkkk').status_code, 200)
        self.assertEqual(self._deposer(telephone='abc12345').status_code, 200)
        self.assertFalse(Candidature.objects.exists())
        self._deposer(whatsapp='+228 91 22 33 44')
        self.assertEqual(Candidature.objects.get().whatsapp, '22891223344')

    def test_email_et_niveaux_obligatoires_page_sans_carte(self):
        self.assertEqual(self._deposer(email='').status_code, 200)
        self.assertEqual(self._deposer(niveaux='').status_code, 200)
        self.assertFalse(Candidature.objects.exists())
        page = self.client.get('/repetiteurs/devenir/').content.decode()
        self.assertNotIn('leaflet', page)
        self.assertNotIn('id_piece_verso', page)
        self.assertIn('required', page)

    def test_piece_reservee_a_l_equipe(self):
        self._deposer()
        c = Candidature.objects.get()
        self.assertIn(self.client.get(f'/repetiteurs/piece/{c.pk}/recto/').status_code, (302, 404))
        u = get_user_model().objects.create_user(email='simple@example.com', password='x-Pass-12345')
        self.client.force_login(u)
        self.assertEqual(self.client.get(f'/repetiteurs/piece/{c.pk}/recto/').status_code, 404)
        admin = get_user_model().objects.create_superuser(email='ad@example.com', password='x-Pass-12345')
        self.client.force_login(admin)
        r = self.client.get(f'/repetiteurs/piece/{c.pk}/recto/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Cache-Control'], 'private, no-store')
        r.close()
        self.assertNotIn('piece', str(self.client.get('/api/mobile/v1/repetiteurs/').json()))

    def test_rejet_et_purge_des_pieces(self):
        from datetime import timedelta
        from django.utils import timezone
        self._deposer()
        c = Candidature.objects.get()
        candidatures.rejeter(c, "Dossier incomplet", 'admin')
        self.assertEqual(candidatures.purger_pieces(), 0)
        self.assertEqual(candidatures.purger_pieces(timezone.now() + timedelta(days=91)), 1)
        c.refresh_from_db()
        self.assertTrue(c.pieces_supprimees)
        self.assertFalse(c.piece_recto)
        # nouvelle candidature possible après un rejet
        self.assertEqual(self.client.get('/repetiteurs/devenir/').status_code, 200)

    def test_admin_decision_motif_obligatoire(self):
        self._deposer()
        c = Candidature.objects.get()
        self._payer(c)
        admin = get_user_model().objects.create_superuser(email='ad3@example.com', password='x-Pass-12345')
        self.client.force_login(admin)
        url = f'/lantanteAdminTech/Repetiteurs/candidature/{c.pk}/change/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(Repetiteur.objects.count(), 0)
