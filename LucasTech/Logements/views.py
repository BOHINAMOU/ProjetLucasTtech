from django.db.models import F
from django.shortcuts import get_object_or_404, render

from .api import disponibles, filtres, itineraire, message, notre_whatsapp, recherche
from .models import CODES, TYPES, Logement

ICONES = {'wifi': 'fa-wifi', 'clim': 'fa-snowflake', 'ventilateur': 'fa-fan', 'parking': 'fa-square-parking',
          'cuisine': 'fa-kitchen-set', 'douche_interne': 'fa-shower', 'wc_interne': 'fa-toilet', 'carrelage': 'fa-border-all',
          'plafond': 'fa-house', 'forage': 'fa-droplet', 'gardien': 'fa-user-shield', 'cloture': 'fa-dungeon',
          'balcon': 'fa-building', 'tv': 'fa-tv', 'eau_chaude': 'fa-temperature-high', 'groupe': 'fa-bolt'}


def liste(request):
    qs = filtres(disponibles(), request.GET)
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = recherche(qs, q)
    tous = Logement.objects.filter(loue=False)
    return render(request, 'logements/liste.html', {
        'logements': qs[:200], 'q': q, 'g': request.GET,
        'villes': sorted(set(tous.values_list('ville', flat=True)), key=str.lower),
        'types': [(c, n) for c, n in TYPES if c in set(tous.values_list('type', flat=True))],
    })


def detail(request, pk):
    l = get_object_or_404(disponibles(), pk=pk)
    Logement.objects.filter(pk=pk).update(vues=F('vues') + 1)
    return render(request, 'logements/detail.html', {
        'l': l, 'wa': notre_whatsapp(), 'itineraire': itineraire(l),
        'message': message(l, request.build_absolute_uri(l.get_absolute_url())),
        'equip': [(ICONES.get(e, 'fa-check'), CODES[e]) for e in (l.equipements or []) if e in CODES],
    })
