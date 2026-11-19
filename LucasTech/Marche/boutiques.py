"""Site : boutiques des vendeurs actifs (lien vers leur mini-site)."""
from django.shortcuts import render

from .models import Vendeur


def liste(request):
    vendeurs = [v for v in Vendeur.objects.filter(statut='valide').exclude(slug='').order_by('boutique') if v.actif]
    return render(request, 'marche/boutiques.html', {'vendeurs': vendeurs})
