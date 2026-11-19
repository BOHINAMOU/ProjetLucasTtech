"""Passe en « Annulé » les paiements restés en attente plus de 10 minutes (après vérification chez FedaPay)."""
from django.core.management.base import BaseCommand

from Payments.services import expirer_anciens


class Command(BaseCommand):
    help = "Expire les paiements en attente depuis plus de 10 minutes."

    def add_arguments(self, parser):
        parser.add_argument('--minutes', type=int, default=10)

    def handle(self, *args, **o):
        self.stdout.write(f"{expirer_anciens(minutes=o['minutes'], limite=500)} paiement(s) expiré(s).")
