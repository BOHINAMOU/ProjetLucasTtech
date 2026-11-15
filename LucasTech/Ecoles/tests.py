from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Ecole, Filiere, InscriptionEcole, MembreEcole

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
API = '/api/mobile/v1/'
A = '/lantanteAdminTech/'


@override_settings(STORAGES=STORAGES)
class EcolesTests(APITestCase):
    def setUp(self):
        U = get_user_model()
        self.e = Ecole.objects.create(nom='Lycée de Tokoin', type='lycee', ville='Lomé')
        self.autre = Ecole.objects.create(nom='Université de Kara', type='universite', ville='Kara')
        self.f = Filiere.objects.create(ecole=self.e, nom='Série D', frais=50000)
        self.resp = U.objects.create_user(email='resp@example.com', password='x-Pass-12345', is_verified=True)
        self.collab = U.objects.create_user(email='col@example.com', password='x-Pass-12345', is_verified=True)
        MembreEcole.objects.create(ecole=self.e, user=self.resp, role='proprietaire')
        MembreEcole.objects.create(ecole=self.e, user=self.collab)

    def test_api_liste_fiche_et_inscription(self):
        d = self.client.get(API + 'ecoles/?type=lycee').json()
        d = d['resultats'] if isinstance(d, dict) else d
        self.assertEqual([x['nom'] for x in d], ['Lycée de Tokoin'])
        f = self.client.get(f'{API}ecoles/{self.e.slug}/').json()
        self.assertEqual(f['filieres'][0]['nom'], 'Série D')
        r = self.client.post(f'{API}ecoles/{self.e.slug}/inscription/',
                             {'nom': 'Koffi', 'prenom': 'Ama', 'telephone': '90 00 00 00', 'filiere': self.f.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(InscriptionEcole.objects.get().telephone, '+22890000000')
        r = self.client.post(f'{API}ecoles/{self.e.slug}/inscription/',
                             {'nom': 'K', 'prenom': 'Ama2', 'telephone': 'abc'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()['erreurs']), {'nom', 'prenom', 'telephone'})
        self.assertEqual(self.client.get(API + 'recherche/?q=tokoin').json()['groupes'][0]['type'], 'ecole')

    def test_espace_de_l_ecole_limite_a_son_ecole(self):
        self.resp.refresh_from_db()
        self.assertTrue(self.resp.is_staff)
        InscriptionEcole.objects.create(ecole=self.e, nom='Koffi', prenom='Ama', telephone='+22890000000')
        InscriptionEcole.objects.create(ecole=self.autre, nom='Mensah', prenom='Yao', telephone='+22891000000')
        self.client.force_login(self.collab)
        r = self.client.get(A + 'Ecoles/ecole/')
        self.assertContains(r, 'Lycée de Tokoin')
        self.assertNotContains(r, 'Université de Kara')
        r = self.client.get(A + 'Ecoles/inscriptionecole/')
        self.assertContains(r, 'Koffi')
        self.assertNotContains(r, 'Mensah')
        self.assertEqual(self.client.get(f'{A}Ecoles/ecole/{self.autre.pk}/change/').status_code, 302)
        r = self.client.post(A + 'Ecoles/inscriptionecole/',
                             {'action': 'exporter_excel', '_selected_action': list(InscriptionEcole.objects.values_list('pk', flat=True))})
        self.assertIn('spreadsheetml', r['Content-Type'])

    def test_seul_le_responsable_gere_l_equipe(self):
        from .admin import MembreInline
        from django.contrib.admin.sites import site
        from django.test import RequestFactory
        rq = RequestFactory().get('/')
        rq.user = self.collab
        self.assertFalse(MembreInline(Ecole, site).has_add_permission(rq, self.e))
        rq.user = self.resp
        self.assertTrue(MembreInline(Ecole, site).has_add_permission(rq, self.e))


@override_settings(STORAGES=STORAGES)
class CyclesTests(APITestCase):
    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import NouveauteEcole
        U = get_user_model()
        self.e = Ecole.objects.create(nom='Complexe Les Élites', type='lycee', ville='Lomé',
                                      cycles=['primaire', 'lycee', 'superieur'])
        self.calme = Ecole.objects.create(nom='AAA École calme', type='primaire', ville='Lomé', ordre=0)
        self.info = Filiere.objects.create(ecole=self.e, cycle='superieur', nom='Informatique')
        NouveauteEcole.objects.create(ecole=self.e, titre='Bourses 2027', texte='Dossiers ouverts')
        NouveauteEcole.objects.create(ecole=self.calme, titre='Vieille', date=timezone.localdate() - timedelta(days=90))
        self.resp = U.objects.create_user(email='r@example.com', password='x-Pass-12345', is_verified=True)
        MembreEcole.objects.create(ecole=self.e, user=self.resp, role='proprietaire')
        self.url = f'{API}ecoles/{self.e.slug}/inscription/'

    def _post(self, **d):
        base = {'nom': 'Koffi', 'prenom': 'Ama', 'telephone': '90000000'}
        base.update(d)
        return self.client.post(self.url, base, format='multipart')

    def test_fiche_cycles_classes_nouveautes_et_badge(self):
        liste = self.client.get(API + 'ecoles/').json()
        liste = liste['resultats'] if isinstance(liste, dict) else liste
        self.assertEqual(liste[0]['nom'], 'Complexe Les Élites')  # nouveauté récente : en tête
        self.assertEqual([x['nouveau'] for x in liste], [True, False])
        f = self.client.get(f'{API}ecoles/{self.e.slug}/').json()
        self.assertEqual([c['code'] for c in f['cycles']], ['primaire', 'lycee', 'superieur'])
        self.assertEqual(f['classes']['lycee'], ['2nde', '1re', 'Tle'])
        self.assertNotIn('college', f['classes'])
        self.assertEqual(f['nouveautes'][0]['titre'], 'Bourses 2027')
        self.assertEqual(f['filieres'][0]['cycle'], 'superieur')

    def test_inscription_par_cycle_et_document_prive(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.assertEqual(self._post().json()['erreurs']['cycle'], "Choisissez le cycle.")
        self.assertIn('classe', self._post(cycle='lycee', classe='CM2').json()['erreurs'])
        self.assertEqual(self._post(cycle='lycee', classe='Tle').status_code, 201)
        self.assertIn('niveau', self._post(cycle='superieur').json()['erreurs'])
        gros = SimpleUploadedFile('a.pdf', b'%PDF' + b'0' * (5 * 1024 * 1024 + 1), content_type='application/pdf')
        self.assertIn('document', self._post(cycle='superieur', niveau='Bac', document=gros).json()['erreurs'])
        exe = SimpleUploadedFile('a.exe', b'MZ', content_type='application/octet-stream')
        self.assertIn('document', self._post(cycle='superieur', niveau='Bac', document=exe).json()['erreurs'])
        pdf = SimpleUploadedFile('releve.pdf', b'%PDF-1.4 releve', content_type='application/pdf')
        r = self._post(cycle='superieur', niveau='Bac', serie_bac='D', filiere=self.info.pk, document=pdf)
        self.assertEqual(r.status_code, 201, r.content)
        i = InscriptionEcole.objects.get(serie_bac='D')
        self.assertEqual((i.cycle, i.niveau_etudes, i.filiere, bool(i.document)), ('superieur', 'Bac', self.info, True))
        url = f'/ecoles/document/{i.pk}/'
        self.assertEqual(self.client.get(url).status_code, 302)  # anonyme : connexion admin
        autre = get_user_model().objects.create_user(email='x@example.com', password='x-Pass-12345', is_staff=True)
        self.client.force_login(autre)
        self.assertEqual(self.client.get(url).status_code, 404)  # pas de son école
        self.client.force_login(self.resp)
        self.assertEqual(self.client.get(url).status_code, 200)
        r = self.client.post(f'{A}Ecoles/inscriptionecole/', {'action': 'exporter_excel', '_selected_action': [i.pk]})
        self.assertEqual(r.status_code, 200)
        import io
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(r.content)).active
        self.assertIn(f'/ecoles/document/{i.pk}/', ws.cell(row=2, column=13).value)


@override_settings(STORAGES=STORAGES)
class ChampsPersonnalisesTests(APITestCase):
    def setUp(self):
        from .models import ChampEcole
        U = get_user_model()
        self.e = Ecole.objects.create(nom='École Les Palmiers', type='primaire', cycles=['primaire', 'college'],
                                      masquer_email=True)
        self.age = ChampEcole.objects.create(ecole=self.e, libelle='Âge', type='nombre', obligatoire=True, ordre=1)
        self.ne = ChampEcole.objects.create(ecole=self.e, libelle='Né le', type='date', ordre=2)
        self.cantine = ChampEcole.objects.create(ecole=self.e, libelle='Cantine', type='oui_non', ordre=3)
        self.langues = ChampEcole.objects.create(ecole=self.e, libelle='Langues', type='choix_multiple',
                                                 choix='Anglais\nEspagnol\nAllemand', ordre=4, cycle='college')
        self.bulletin = ChampEcole.objects.create(ecole=self.e, libelle='Bulletin', type='fichier', ordre=5,
                                                  cycle='college', obligatoire=True)
        self.resp = U.objects.create_user(email='p@example.com', password='x-Pass-12345', is_verified=True)
        MembreEcole.objects.create(ecole=self.e, user=self.resp, role='proprietaire')
        self.url = f'{API}ecoles/{self.e.slug}/inscription/'

    def _post(self, **d):
        base = {'nom': 'Koffi', 'prenom': 'Ama', 'telephone': '90000000', 'cycle': 'primaire', 'classe': 'CP1'}
        base.update(d)
        return self.client.post(self.url, base, format='multipart')

    def test_definition_et_champs_masques(self):
        f = self.client.get(f'{API}ecoles/{self.e.slug}/').json()
        self.assertEqual([c['libelle'] for c in f['champs']], ['Âge', 'Né le', 'Cantine', 'Langues', 'Bulletin'])
        self.assertEqual(f['champs'][3]['choix'], ['Anglais', 'Espagnol', 'Allemand'])
        self.assertTrue(f['masquer']['email'])

    def test_obligatoire_type_invalide_et_cycle(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        r = self._post()
        self.assertEqual(r.json()['erreurs'][f'champ_{self.age.pk}'], "Obligatoire.")
        r = self._post(**{f'champ_{self.age.pk}': 'six', f'champ_{self.ne.pk}': '31/02/2020'})
        self.assertEqual((r.json()['erreurs'][f'champ_{self.age.pk}'], r.json()['erreurs'][f'champ_{self.ne.pk}']),
                         ("Nombre attendu.", "Date invalide."))
        # au primaire, les champs du collège ne sont pas demandés
        r = self._post(**{f'champ_{self.age.pk}': '6', f'champ_{self.cantine.pk}': 'oui', 'email': 'x@example.com'})
        self.assertEqual(r.status_code, 201, r.content)
        i = InscriptionEcole.objects.latest('pk')
        self.assertEqual(i.reponses[str(self.cantine.pk)]['valeur'], 'Oui')
        self.assertEqual(i.email, '')  # e-mail masqué par l'école
        # au collège : choix multiple contrôlé et fichier obligatoire
        r = self._post(cycle='college', classe='6e', **{f'champ_{self.age.pk}': '11', f'champ_{self.langues.pk}': 'Anglais|Chinois'})
        self.assertEqual(r.json()['erreurs'][f'champ_{self.langues.pk}'], "Choix invalide.")
        self.assertEqual(r.json()['erreurs'][f'champ_{self.bulletin.pk}'], "Obligatoire.")
        pdf = SimpleUploadedFile('bulletin.pdf', b'%PDF-1.4 x', content_type='application/pdf')
        r = self._post(cycle='college', classe='6e', **{f'champ_{self.age.pk}': '11',
                                                        f'champ_{self.langues.pk}': 'Anglais|Espagnol',
                                                        f'champ_{self.bulletin.pk}': pdf})
        self.assertEqual(r.status_code, 201, r.content)
        i = InscriptionEcole.objects.latest('pk')
        self.assertEqual(i.reponses[str(self.langues.pk)]['valeur'], ['Anglais', 'Espagnol'])
        self.assertEqual(i.fichiers.count(), 1)

    def test_admin_et_export_avec_colonnes(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        pdf = SimpleUploadedFile('bulletin.pdf', b'%PDF-1.4 x', content_type='application/pdf')
        self._post(cycle='college', classe='5e', **{f'champ_{self.age.pk}': '12', f'champ_{self.bulletin.pk}': pdf})
        i = InscriptionEcole.objects.get()
        self.client.force_login(self.resp)
        self.assertContains(self.client.get(f'{A}Ecoles/inscriptionecole/{i.pk}/change/'), 'Âge')
        r = self.client.post(f'{A}Ecoles/inscriptionecole/', {'action': 'exporter_excel', '_selected_action': [i.pk]})
        import io
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(r.content)).active
        entetes = [c.value for c in ws[1]]
        self.assertEqual(entetes[-5:], ['Âge', 'Né le', 'Cantine', 'Langues', 'Bulletin'])
        ligne = [c.value for c in ws[2]]
        self.assertEqual(ligne[entetes.index('Âge')], '12')
        self.assertIn('/ecoles/fichier/', ligne[entetes.index('Bulletin')])
        f = i.fichiers.get()
        self.assertEqual(self.client.get(f'/ecoles/fichier/{f.pk}/').status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(f'/ecoles/fichier/{f.pk}/').status_code, 302)
