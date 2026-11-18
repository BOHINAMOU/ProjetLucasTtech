"""Accès admin d'un vendeur validé : ses produits et ses ventes seulement."""
PERMS = [('Shop', 'product', ('view', 'add', 'change')), ('Shop', 'productimage', ('view', 'add', 'change', 'delete')),
         ('Payments', 'payment', ('view',)), ('Marche', 'vendeur', ('view',)), ('Marche', 'reversement', ('view',)),
         ('Marche', 'categorievendeur', ('view', 'add', 'change', 'delete')), ('Shop', 'product', ('delete',))]
GROUPE = "Vendeur"


def donner_acces(user):
    from django.contrib.auth.models import Group, Permission
    g, _ = Group.objects.get_or_create(name=GROUPE)
    for app, model, actions in PERMS:
        g.permissions.add(*Permission.objects.filter(content_type__app_label=app, content_type__model=model,
                                                     codename__in=[f'{a}_{model}' for a in actions]))
    user.groups.add(g)
    if not user.is_staff:
        user.is_staff = True
        user.save(update_fields=['is_staff'])


def vendeur_de(user):
    """Le vendeur lié à ce compte, quel que soit son statut (None pour l'équipe ou un simple client).
    Un vendeur suspendu ou expiré reste limité à SES produits (et l'admin lui est fermé : voir core.admin)."""
    if not getattr(user, 'is_authenticated', False) or user.is_superuser:
        return None
    from .models import Vendeur
    return Vendeur.objects.filter(user=user).first()
