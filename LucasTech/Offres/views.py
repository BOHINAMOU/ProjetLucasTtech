"""Site : liste et détail des offres ; on contacte directement le recruteur."""
from django.shortcuts import get_object_or_404, render

from .api import _wa, actives
from .models import OffreEmploi


def liste(request):
    return render(request, 'offres/liste.html', {'offres': actives()})


def detail(request, pk):
    o = get_object_or_404(actives(), pk=pk)
    from django.db.models import F
    OffreEmploi.objects.filter(pk=pk).update(vues=F('vues') + 1)
    wa = _wa(o.whatsapp)
    return render(request, 'offres/detail.html', {'o': o, 'wa': wa})
