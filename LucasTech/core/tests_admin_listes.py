"""Toutes les pages de liste de l'admin s'ouvrent (200), avec au moins une ligne dans les listes courantes.
Régression du 21/11/2026 : Admin › Actualités en erreur 500 dès qu'il y avait un article."""
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}


@override_settings(STORAGES=STORAGES)
class ListesAdminTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(email='adm@example.com', password='x-Pass-12345')
        self.client.force_login(self.admin)
        from Publications.models import Publication, PublicationLike
        p = Publication.objects.create(title='Titre', slug='titre', content='x', is_published=True, author=self.admin)
        PublicationLike.objects.create(publication=p, user=self.admin)
        from courses.models import Categorie, Course
        Course.objects.create(client=self.admin, categorie=Categorie.objects.get(code='moto'), depart_lat=6.13, depart_lng=1.22,
                              arrivee_lat=6.16, arrivee_lng=1.22, distance_km=4, duree_min=10, prix_estime=700)

    def test_actualites_avec_un_article(self):
        r = self.client.get(reverse('admin:Publications_publication_changelist'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Titre')

    def test_toutes_les_listes(self):
        erreurs = []
        for m in admin.site._registry:
            url = reverse(f'admin:{m._meta.app_label}_{m._meta.model_name}_changelist')
            try:
                code = self.client.get(url).status_code
            except Exception as e:  # pragma: no cover - affiché en cas d'échec
                code = repr(e)[:200]
            if code not in (200, 302):
                erreurs.append((url, code))
        self.assertEqual(erreurs, [])

    def test_gestion_des_courses_dans_la_barre(self):
        r = self.client.get('/lantanteAdminTech/section/courses/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Gestion des courses')

    def test_comptes_par_categorie(self):
        from courses.models import Categorie, CompteClient, CompteCoursier, CompteSysteme, Partenaire
        U = get_user_model()
        cli = U.objects.create_user(email='client@example.com', password='x-Pass-12345')
        cou = U.objects.create_user(email='coursier@example.com', password='x-Pass-12345')
        p = Partenaire.objects.create(user=cou, plaque='TG 1')
        p.categories.add(Categorie.objects.get(code='moto'))
        self.assertIn(cli, CompteClient.objects.all())
        # catégories séparées : le coursier n'est pas dans les clients, l'équipe n'est nulle part ailleurs
        self.assertNotIn(cou, CompteClient.objects.all())
        self.assertNotIn(self.admin, CompteClient.objects.all())
        self.assertNotIn(self.admin, CompteCoursier.objects.all())
        self.assertEqual(list(CompteCoursier.objects.all()), [CompteCoursier.objects.get(pk=cou.pk)])
        self.assertEqual(list(CompteSysteme.objects.values_list('email', flat=True)), ['adm@example.com'])
        for nom in ('compteclient', 'comptecoursier', 'comptesysteme', 'comptevendeur'):
            r = self.client.get(reverse(f'admin:courses_{nom}_changelist'))
            self.assertEqual(r.status_code, 200, nom)
        r = self.client.get(reverse('admin:courses_comptecoursier_changelist'))
        self.assertContains(r, 'coursier@example.com')
        self.assertContains(r, 'Moto')
