from urllib.parse import quote

from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .api import fiche, itineraire, visibles, whatsapp
from .models import Restaurant


def _wa_inscription():
    from api_mobile.catalog import _wa_valide, _whatsapp_lantante
    wa = _wa_valide(_whatsapp_lantante())
    return f"https://wa.me/{wa}?text={quote('Bonjour, je veux inscrire mon restaurant sur Lantante.')}" if wa else ''


def liste(request):
    qs = visibles()
    q = (request.GET.get('q') or '').strip()
    if q:
        from api_mobile.recherche import filtrer
        qs = filtrer(qs, q, 'nom', 'quartier', 'ville', 'plats__nom').distinct()
    return render(request, 'restaurants/liste.html', {'restaurants': qs[:200], 'q': q, 'inscription': _wa_inscription()})


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
