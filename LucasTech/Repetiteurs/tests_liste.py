from django.test import TestCase, override_settings

from core.models import SiteSettings

from .models import Repetiteur


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class ListePubliqueTests(TestCase):
    def test_page_cartes_etapes_et_devenir(self):
        s = SiteSettings.load()
        s.whatsapp_1 = '+228 92 96 77 87'
        s.save()
        Repetiteur.objects.create(nom='Mathématiques — Terminale C/D', matieres='Mathématiques', niveaux='Tle C, Tle D',
                                  ville='Lomé et environs', est_service_lantante=True)
        Repetiteur.objects.create(nom='Caché', matieres='SVT', ville='Lomé', actif=False)
        r = self.client.get('/repetiteurs/')
        self.assertContains(r, 'Mathématiques — Terminale C/D')
        self.assertNotContains(r, 'Caché')
        self.assertContains(r, 'wa.me/22892967787')
        self.assertContains(r, 'On vous propose un répétiteur')
        self.assertContains(r, 'Devenir répétiteur de maison')
        self.assertNotContains(self.client.get('/repetiteurs/?matiere=SVT'), 'Terminale C/D')
