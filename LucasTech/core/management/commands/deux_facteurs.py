"""Secours pour la connexion en deux étapes de l'admin.

    python manage.py deux_facteurs desactiver email@exemple.com   # ce compte n'a plus besoin du code
    python manage.py deux_facteurs reactiver email@exemple.com
    python manage.py deux_facteurs test email@exemple.com         # envoie un e-mail de test (sans connexion)
"""
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

from core.models import Exemption2FA


class Command(BaseCommand):
    help = "Désactive / réactive le code par e-mail d'un compte admin, ou teste l'envoi d'e-mail."

    def add_arguments(self, parser):
        parser.add_argument('action', choices=['desactiver', 'reactiver', 'test'])
        parser.add_argument('email')

    def handle(self, action, email, **o):
        user = get_user_model().objects.filter(email__iexact=email).first()
        if not user:
            raise CommandError("Aucun compte avec cette adresse.")
        if action == 'desactiver':
            Exemption2FA.objects.get_or_create(user=user, defaults={'motif': 'commande de secours'})
            self.stdout.write("Code par e-mail désactivé pour ce compte.")
        elif action == 'reactiver':
            Exemption2FA.objects.filter(user=user).delete()
            self.stdout.write("Code par e-mail réactivé pour ce compte.")
        else:
            send_mail("Test : connexion à l'administration Lantante",
                      "Bonjour,\n\nCeci est un e-mail de test : les codes de connexion à l'administration "
                      "vous seront envoyés à cette adresse.\n\nL'équipe Lantante", None, [user.email])
            self.stdout.write("E-mail de test envoyé.")
