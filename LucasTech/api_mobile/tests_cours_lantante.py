from django.test import TestCase, override_settings

from core.models import SiteSettings
from Repetiteurs.models import Repetiteur


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class CoursLantanteTests(TestCase):
    def test_cours_lantante_apres_les_vrais_et_contact_lantante(self):
        s = SiteSettings.load()
        s.whatsapp_1 = '+228 90 11 77 87'
        s.save()
        c = Repetiteur(nom='Mathématiques — Terminale C/D', matieres='Mathématiques', ville='Lomé et environs',
                       est_service_lantante=True, ordre=0)
        c.full_clean()  # pas de WhatsApp exigé pour une fiche Lantante
        c.save()
        Repetiteur.objects.create(nom='Koffi', matieres='Anglais', ville='Lomé', whatsapp='22890000001', ordre=5)
        r = self.client.get('/api/mobile/v1/repetiteurs/').json()['resultats']
        self.assertEqual([x['nom'] for x in r], ['Koffi', 'Mathématiques — Terminale C/D'])
        self.assertEqual(r[1]['whatsapp'], '22890117787')
        self.assertEqual(r[1]['intervenant'], 'Lantante Répétiteurs')
        self.assertEqual(r[1]['message_whatsapp'], 'Bonjour, je cherche un répétiteur : Mathématiques — Terminale C/D.')
        d = self.client.get(f'/api/mobile/v1/repetiteurs/{c.pk}/').json()
        self.assertEqual(d['telephone'], '+22890117787')
        self.assertEqual(r[0]['whatsapp'], '22890000001')
