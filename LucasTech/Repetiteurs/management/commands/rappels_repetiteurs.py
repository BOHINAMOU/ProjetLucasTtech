"""Prévient par e-mail les répétiteurs dont l'affichage se termine dans 7 jours (à planifier chaque jour)."""
from django.core.management.base import BaseCommand

from Repetiteurs.candidatures import rappeler_fins


class Command(BaseCommand):
    help = "Rappel 7 jours avant la fin d'affichage d'un répétiteur."

    def handle(self, *a, **o):
        self.stdout.write(f"{rappeler_fins()} rappel(s)")
