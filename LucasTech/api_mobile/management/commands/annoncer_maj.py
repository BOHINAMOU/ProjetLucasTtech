"""Notification push « Nouvelle version disponible » à tous les téléphones qui ont l'APK du site."""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from api_mobile.push import SUJET_MAJ, envoyer_sujet


class Command(BaseCommand):
    help = "Annonce la version publiée (media/app/version.json) par notification push."

    def handle(self, *args, **opts):
        with open(os.path.join(settings.MEDIA_ROOT, 'app', 'version.json'), encoding='utf-8') as fh:
            v = json.load(fh)
        ok = envoyer_sujet(SUJET_MAJ, "Nouvelle mise à jour disponible",
                           "Touchez pour mettre à jour.",
                           {'type': 'maj', 'build': v.get('build', 0)})
        self.stdout.write("Notification envoyée." if ok else "Notification non envoyée (voir les journaux).")
