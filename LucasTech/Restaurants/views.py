from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .api import fiche, itineraire, visibles, whatsapp
from .models import Restaurant


def liste(request):
    qs = visibles()
    q = (request.GET.get('q') or '').strip()
    if q:
        from api_mobile.recherche import filtrer
        qs = filtrer(qs, q, 'nom', 'quartier', 'ville', 'adresse', 'plats__nom').distinct()
    return render(request, 'restaurants/liste.html', {'restaurants': qs[:200], 'q': q})


def detail(request, slug):
    r = get_object_or_404(visibles(), slug=slug)
    Restaurant.objects.filter(pk=r.pk).update(vues=F('vues') + 1)
    d = fiche(request, r)
    return render(request, 'restaurants/detail.html', {'r': r, 'd': d, 'wa': whatsapp(r), 'itineraire': itineraire(r)})


@csrf_exempt
@require_POST
def clic(request, slug):
    Restaurant.objects.filter(slug=slug).update(clics_commander=F('clics_commander') + 1)
    return JsonResponse({'ok': True})


def credits_photos(request):
    """Auteurs et licences des photos libres utilisées (obligatoire pour les licences CC BY / BY-SA)."""
    import json
    import os

    from django.conf import settings
    try:
        with open(os.path.join(settings.MEDIA_ROOT, 'restaurants', 'photos-libres', 'credits.json'), encoding='utf-8') as f:
            credits = sorted(json.load(f).values(), key=lambda c: c.get('fichier', ''))
    except (OSError, ValueError):
        credits = []
    return render(request, 'restaurants/credits.html', {'credits': credits})
