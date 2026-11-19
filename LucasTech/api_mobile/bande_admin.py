"""Actions « Mettre sur la bande » / « Retirer de la bande » ajoutées aux listes de l'admin (une seule bande : CarouselItem)."""
from django.contrib import admin, messages
from django.db.models import Max

CIBLES = {
    'core.Partner': 'partenaire', 'Publications.Publication': 'publication', 'Events.Event': 'evenement',
    'Offres.OffreEmploi': 'emploi', 'Formations.Formation': 'formation', 'Hotels.Hotel': 'hotel',
    'Restaurants.Restaurant': 'restaurant', 'Shop.Product': 'produit', 'Ecoles.Ecole': 'ecole',
    'Services.Service': 'service', 'Marche.Vendeur': 'vendeur', 'concours.Contest': 'concours',
}


def _action_mettre(cible):
    def mettre(modeladmin, request, queryset):
        from .models import CarouselItem
        ordre = (CarouselItem.objects.aggregate(m=Max('ordre'))['m'] or 0) + 1
        n = 0
        for o in queryset:
            c, cree = CarouselItem.objects.get_or_create(cible=cible, cible_id=o.pk, defaults={'ordre': ordre, 'actif': True})
            if not cree and not c.actif:
                c.actif = True
                c.save(update_fields=['actif'])
            ordre += 1
            n += 1
        from django.core.cache import cache
        cache.clear()
        messages.success(request, f"{n} élément(s) sur la bande de l'appli. Ordre et image : Notifications › Bande de l'appli.")
    mettre.short_description = "Mettre sur la bande de l'appli"
    mettre.__name__ = 'mettre_sur_la_bande'
    return mettre


def _action_retirer(cible):
    def retirer(modeladmin, request, queryset):
        from .models import CarouselItem
        n = CarouselItem.objects.filter(cible=cible, cible_id__in=list(queryset.values_list('pk', flat=True))).update(actif=False)
        from django.core.cache import cache
        cache.clear()
        messages.success(request, f"{n} élément(s) retiré(s) de la bande de l'appli.")
    retirer.short_description = "Retirer de la bande de l'appli"
    retirer.__name__ = 'retirer_de_la_bande'
    return retirer


def brancher():
    from django.apps import apps
    for label, cible in CIBLES.items():
        try:
            m = apps.get_model(label)
        except LookupError:
            continue
        ma = admin.site._registry.get(m)
        if not ma:
            continue
        actions = list(ma.actions or [])
        actions += [_action_mettre(cible), _action_retirer(cible)]
        ma.actions = actions
