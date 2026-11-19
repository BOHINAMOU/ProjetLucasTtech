from django.db.models import F
from django.shortcuts import get_object_or_404, render

from .api import disponibles, fiches, filtres, itineraire, lien_fiche, message, notre_whatsapp, recherche
from .models import CODES, TYPES, FicheLogement, Logement

ICONES = {'wifi': 'fa-wifi', 'clim': 'fa-snowflake', 'ventilateur': 'fa-fan', 'parking': 'fa-square-parking',
          'cuisine': 'fa-kitchen-set', 'douche_interne': 'fa-shower', 'wc_interne': 'fa-toilet', 'carrelage': 'fa-border-all',
          'plafond': 'fa-house', 'forage': 'fa-droplet', 'gardien': 'fa-user-shield', 'cloture': 'fa-dungeon',
          'balcon': 'fa-building', 'tv': 'fa-tv', 'eau_chaude': 'fa-temperature-high', 'groupe': 'fa-bolt'}


def liste(request):
    qs = filtres(disponibles(), request.GET)
    q = (request.GET.get('q') or '').strip()
    if q:
        qs = recherche(qs, q)
    tous = Logement.objects.visibles()
    toutes = FicheLogement.objects.filter(visible=True)
    lf = list(fiches(request.GET))
    for f in lf:
        f.lien = lien_fiche(f)
    return render(request, 'logements/liste.html', {
        'logements': qs[:200], 'q': q, 'g': request.GET, 'fiches': lf, 'annonces': tous.exists(),
        'fiche_types': sorted(set(toutes.values_list('type_libelle', flat=True)), key=str.lower),
        'quartiers': sorted(set(toutes.values_list('quartier', flat=True)), key=str.lower),
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


def credits_photos(request):
    vus, credits = set(), []
    for c in FicheLogement.objects.filter(visible=True).exclude(credit_photo='').values_list('credit_photo', flat=True):
        if c in vus:
            continue
        vus.add(c)
        titre, auteur, licence, page = (c.split(' — ') + ['', '', '', ''])[:4]
        credits.append({'fichier': titre, 'auteur': auteur, 'licence': licence, 'page': page})
    return render(request, 'restaurants/credits.html', {'credits': credits, 'rubrique': 'Location', 'sujet': 'des logements'})
