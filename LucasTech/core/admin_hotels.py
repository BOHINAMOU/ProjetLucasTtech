"""Hôtels dans l'admin : liste en cartes (page de la rubrique) et fiche détaillée de chaque hôtel avec ses chambres."""
from urllib.parse import quote

from django.contrib import admin as _admin
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse


def _f(n):
    return f"{int(n):,} CFA".replace(',', ' ') if n else '—'


def cartes(request):
    from Hotels.models import Hotel
    if not request.user.has_perm('Hotels.view_hotel'):
        return []
    return list(Hotel.objects.all().prefetch_related('chambres').order_by('ordre', 'nom'))


@staff_member_required
def fiche(request, pk):
    from Hotels.models import CODES, Hotel
    if not request.user.has_perm('Hotels.view_hotel'):
        raise Http404
    h = Hotel.objects.filter(pk=pk).prefetch_related('photos', 'chambres__photos').first()
    if not h:
        raise Http404
    ici = reverse('admin_hotel', args=[h.pk])
    chambres = []
    for c in h.chambres.all():
        p = c.photos.first()
        chambres.append({
            'c': c, 'photo': p.image.url if p else '', 'prix': _f(c.prix_nuit),
            'modifier': reverse('admin:Hotels_chambre_change', args=[c.pk]) + f'?retour={quote(ici)}',
            'supprimer': reverse('admin:Hotels_chambre_delete', args=[c.pk]) + f'?retour={quote(ici)}',
        })
    ctx = dict(_admin.site.each_context(request), title=h.nom, h=h, chambres=chambres,
               equipements=[CODES[e] for e in (h.equipements or []) if e in CODES],
               kpis=[("Vues", h.vues), ("Clics Réserver", h.clics_reserver), ("Clics Appeler", h.clics_appel),
                     ("Chambres", len(chambres)), ("À partir de", _f(h.a_partir_de))],
               liens={
                   'modifier': reverse('admin:Hotels_hotel_change', args=[h.pk]) + f'?retour={quote(ici)}',
                   'ajouter': reverse('admin:Hotels_chambre_add') + f'?hotel={h.pk}&retour={quote(ici)}',
                   'site': h.get_absolute_url(),
               })
    return render(request, 'admin/hotel.html', ctx)
