"""Rôles délégués : droits d'accès à l'admin et périmètre (ce que chaque délégué voit)."""
from django.db.models import Q

PERMS = {
    'evenement': [('Events', 'event', ('view', 'change')), ('Events', 'tickettype', ('view', 'add', 'change')),
                  ('Events', 'ticket', ('view',)), ('Payments', 'payment', ('view', 'delete'))],
    'service': [('Services', 'service', ('view', 'change')), ('Services', 'champinscription', ('view', 'add', 'change', 'delete')),
                ('Services', 'inscriptionservice', ('view', 'change')), ('Payments', 'payment', ('view',))],
    'publications': [('Publications', m, ('view', 'add', 'change', 'delete'))
                     for m in ('publication', 'publicationcategory', 'publicationcomment')],
}


def appliquer(d):
    """Donne au délégué l'accès à l'admin et les permissions de son rôle (groupe dédié)."""
    from django.contrib.auth.models import Group, Permission
    if d.type == 'ecole' and d.ecole_id:
        from Ecoles.models import MembreEcole
        MembreEcole.objects.get_or_create(ecole_id=d.ecole_id, user=d.user, defaults={'role': 'collaborateur'})
        return
    g, _ = Group.objects.get_or_create(name=f"Délégué : {dict(d.TYPES)[d.type].split(' (')[0]}")
    for app, model, actions in PERMS.get(d.type, []):
        g.permissions.add(*Permission.objects.filter(content_type__app_label=app, content_type__model=model,
                                                     codename__in=[f'{a}_{model}' for a in actions]))
    d.user.groups.add(g)
    if not d.user.is_staff:
        d.user.is_staff = True
        d.user.save(update_fields=['is_staff'])


def ids(user, type):
    if not user.is_authenticated:
        return []
    champ = {'evenement': 'event_id', 'service': 'service_id', 'ecole': 'ecole_id'}[type]
    return [x for x in user.delegations.filter(type=type).values_list(champ, flat=True) if x]


def evenements_visibles(user, qs):
    if user.is_superuser:
        return qs
    return qs.filter(Q(organizer=user) | Q(pk__in=ids(user, 'evenement')))


def paiements_visibles(user, qs):
    if user.is_superuser:
        return qs
    from Events.models import Event
    evts = evenements_visibles(user, Event.objects.all()).values_list('pk', flat=True)
    return qs.filter(Q(event_id__in=evts) | Q(service_id__in=ids(user, 'service')))


def services_visibles(user, qs):
    if user.is_superuser:
        return qs
    return qs.filter(pk__in=ids(user, 'service'))
