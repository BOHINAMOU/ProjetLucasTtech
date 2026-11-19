"""Site : liste des écoles (logo d'abord) et fiche d'une école avec ses filières."""
from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from .models import Ecole, lien_inscription


def _publiees():
    return Ecole.objects.filter(publie=True)


def liste(request):
    qs = _publiees().annotate(nb_filieres=Count('filieres')).order_by('ordre', 'nom')
    q = (request.GET.get('q') or '').strip()
    if q:
        from api_mobile.recherche import filtrer
        qs = filtrer(qs, q, 'nom', 'ville', 'filieres__nom', alias='alias')
    return render(request, 'ecoles/liste.html', {'ecoles': qs, 'q': q})


def fiche(request, slug):
    e = get_object_or_404(_publiees().prefetch_related('filieres'), slug=slug)
    return render(request, 'ecoles/fiche.html', {'e': e, 'filieres': e.filieres.order_by('ordre', 'pk'),
                                                  'inscription': lien_inscription(e)})
