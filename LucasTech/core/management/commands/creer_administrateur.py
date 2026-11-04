"""Donne le rôle « Administrateur » à un compte existant.

    python manage.py creer_administrateur personne@exemple.com

Le compte devient membre de l'équipe (is_staff), sans être super administrateur, et rejoint le
groupe « Administrateur ». Un super administrateur n'est jamais modifié par cette commande.
Le mot de passe n'est pas touché.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from .setup_roles import GROUP_NAME


class Command(BaseCommand):
    help = "Donne le rôle « Administrateur » (équipe, sans super-pouvoirs) à un compte existant."

    def add_arguments(self, parser):
        parser.add_argument('email')

    def handle(self, *args, email, **options):
        User = get_user_model()
        try:
            user = User.objects.get(email__iexact=email.strip())
        except User.DoesNotExist:
            raise CommandError(f"Aucun compte avec l'adresse {email}. La personne doit d'abord créer son compte.")
        if user.is_superuser:
            raise CommandError(f"{user.email} est super administrateur : compte laissé tel quel.")
        if not Group.objects.filter(name=GROUP_NAME).exists():
            call_command('setup_roles', verbosity=0)
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        user.groups.add(Group.objects.get(name=GROUP_NAME))
        self.stdout.write(self.style.SUCCESS(f"{user.email} a maintenant le rôle « {GROUP_NAME} »."))
