"""Crée / met à jour le rôle « Administrateur » (groupe Django), de façon idempotente.

    python manage.py setup_roles

Le rôle peut consulter, ajouter et modifier tout le contenu du site (publications, offres,
candidatures, messages, commentaires, boutique, formations, portfolio, réglages…), mais :
  • AUCUNE permission de suppression (delete_*) ;
  • AUCUNE permission sur les comptes et les droits (Users.*, auth.*, contenttypes, sessions,
    admin.LogEntry, jetons d'API, comptes sociaux) ;
  • le bannissement de comptes reste réservé au super administrateur (Emploi.AccountBan : lecture seule).
Les permissions du groupe sont remplacées à chaque exécution : relancer la commande après
l'ajout d'un modèle suffit à mettre le rôle à jour.
"""
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

GROUP_NAME = "Administrateur"

# Applications dont le contenu est géré par le rôle.
CONTENT_APPS = ('core', 'Publications', 'Services', 'Portfolio', 'Shop', 'Formations', 'Emploi')

# Modèles exclus totalement (app_label, model) : jetons d'appareil = données techniques.
EXCLUDED_MODELS = {('Emploi', 'devicetoken')}

# Modèles en lecture seule pour le rôle.
VIEW_ONLY_MODELS = {('Emploi', 'accountban')}


def role_permissions():
    perms = Permission.objects.filter(content_type__app_label__in=CONTENT_APPS).select_related('content_type')
    keep = []
    for perm in perms:
        key = (perm.content_type.app_label, perm.content_type.model)
        action = perm.codename.split('_', 1)[0]
        if key in EXCLUDED_MODELS or action == 'delete':
            continue
        if action not in ('view', 'add', 'change'):
            continue  # permissions personnalisées éventuelles : non accordées par défaut
        if key in VIEW_ONLY_MODELS and action != 'view':
            continue
        keep.append(perm)
    return keep


class Command(BaseCommand):
    help = "Crée / met à jour le groupe « Administrateur » (contenu : voir, ajouter, modifier ; jamais supprimer ni gérer les comptes)."

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name=GROUP_NAME)
        perms = role_permissions()
        group.permissions.set(perms)
        self.stdout.write(self.style.SUCCESS(
            f"Groupe « {GROUP_NAME} » {'créé' if created else 'mis à jour'} : {len(perms)} permissions."))
        if options.get('verbosity', 1) >= 2:
            for p in sorted(perms, key=lambda p: (p.content_type.app_label, p.codename)):
                self.stdout.write(f"  {p.content_type.app_label}.{p.codename}")
