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
        self.u = get_user_model().objects.create_user(email='prof@example.com', password='x-Pass-12345')
        self.client.force_login(self.u)

    def _deposer(self, **extra):
        d = {'prenom': 'Kossi', 'nom': 'Mensah', 'telephone': '90000000', 'whatsapp': '22890000000',
             'email': 'prof@example.com', 'matieres': 'Maths, Physique', 'niveaux': 'Tle', 'ville': 'Lomé',
             'quartier': 'Bè', 'piece_type': 'cni', 'piece_numero': 'A123',
             'photo': _image(), 'piece_recto': _pdf('recto.pdf'), 'piece_verso': _pdf('verso.pdf')}
        d.update(extra)
        return self.client.post('/repetiteurs/devenir/', d)

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
        self.assertEqual(self.client.get('/repetiteurs/ma-candidature/').status_code, 200)

    def test_correction_sans_repayer(self):
        self._deposer()
        c = Candidature.objects.get()
        self._payer(c)
        c.refresh_from_db()
        candidatures.demander_correction(c, "Photo floue", 'admin')
        self.assertContains(self.client.get('/repetiteurs/devenir/'), 'Photo floue')
        r = self._deposer(photo=_image('nette.png'))
        self.assertEqual(r['Location'], '/repetiteurs/ma-candidature/')
        c.refresh_from_db()
        self.assertEqual(c.statut, 'a_verifier')
        self.assertEqual(Payment.objects.filter(kind='candidature').count(), 1)

    def test_verso_obligatoire_pour_la_cni(self):
        r = self._deposer(piece_verso='')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Candidature.objects.exists())

    def test_piece_reservee_a_l_equipe(self):
        self._deposer()
        c = Candidature.objects.get()
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
