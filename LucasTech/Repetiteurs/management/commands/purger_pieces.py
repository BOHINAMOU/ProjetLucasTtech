"""Supprime les pièces d'identité des candidatures 90 jours après la décision finale (à planifier chaque jour)."""
from django.core.management.base import BaseCommand

from Repetiteurs.candidatures import purger_pieces


class Command(BaseCommand):
    help = "Supprime les pièces d'identité 90 jours après la décision."

    def handle(self, *a, **o):
        self.stdout.write(f"{purger_pieces()} pièce(s) supprimée(s)")
