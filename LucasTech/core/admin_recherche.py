"""Recherche globale de l'administration (barre du haut) : cherche dans les principaux éléments, avec les droits de chacun."""
from django.apps import apps
from django.contrib import admin as _admin
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.urls import reverse

# (modèle, libellé du groupe, icône Material)
CIBLES = [
    ('Hotels.Hotel', "Hôtels", 'hotel'), ('Shop.Product', "Produits", 'storefront'), ('Users.User', "Utilisateurs", 'person'),
    ('Payments.Payment', "Paiements", 'payments'), ('Publications.Publication', "Actualités", 'newspaper'),
    ('Events.Event', "Événements", 'event'), ('Formations.Formation', "Formations", 'school'),
    ('Services.Service', "Services", 'design_services'), ('Ecoles.Ecole', "Écoles", 'account_balance'),
    ('Offres.OffreEmploi', "Emplois", 'work'), ('Marche.Vendeur', "Vendeurs", 'store'),
    ('Logements.Logement', "Location", 'house'), ('Repetiteurs.Repetiteur', "Répétiteurs", 'person_book'),
    ('concours.Contest', "Concours", 'quiz'),
]
FICHES = {'Hotels.Hotel': ('admin_hotel', None), 'Ecoles.Ecole': ('admin_fiche', 'ecoles'),
          'Marche.Vendeur': ('admin_fiche', 'vendeurs'), 'Events.Event': ('admin_evenement', None)}


def _lien(label, o):
    if label in FICHES:
        nom, code = FICHES[label]
        return reverse(nom, args=[code, o.pk] if code else [o.pk])
    return reverse(f'admin:{o._meta.app_label}_{o._meta.model_name}_change', args=[o.pk])


@staff_member_required
def recherche(request):
    q = (request.GET.get('q') or '').strip()[:80]
    groupes, total = [], 0
    if len(q) >= 2:
        for label, titre, icone in CIBLES:
            try:
                m = apps.get_model(label)
            except LookupError:
                continue
            ma = _admin.site._registry.get(m)
            if not ma or not ma.get_search_fields(request) or not ma.has_view_or_change_permission(request):
                continue
            try:
                qs, _dup = ma.get_search_results(request, ma.get_queryset(request), q)
                n = qs.count()
                objs = list(qs.distinct()[:8])
            except Exception:
                continue
            if n:
                total += n
                url_liste = reverse(f'admin:{m._meta.app_label}_{m._meta.model_name}_changelist') + f'?q={q}'
                groupes.append({'titre': titre, 'icone': icone, 'n': n, 'tout': url_liste,
                                'objs': [{'t': str(o)[:90], 'url': _lien(label, o)} for o in objs]})
    return render(request, 'admin/recherche.html', dict(_admin.site.each_context(request), title="Recherche",
                                                        q=q, groupes=groupes, total=total))
