"""Envoie un exemple de chaque e-mail du site à une adresse (pour valider le gabarit)."""
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Envoie un exemple de chaque e-mail du site à l'adresse donnée."

    def add_arguments(self, parser):
        parser.add_argument('email')

    def handle(self, email, **o):
        from core.exemples_emails import EXEMPLES
        for sujet, corps in EXEMPLES:
            send_mail(f"[Exemple] {sujet}", corps, None, [email])
        self.stdout.write(f"{len(EXEMPLES)} exemples envoyés.")
