"""Répétiteur - École : liste (recherche, filtres matière / ville) et fiche avec contacts."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .catalog import grande, public_cache, text, vignette
from .utils import error


def item(request, r):
    return {'id': r.pk, 'nom': r.nom, 'photo': vignette(request, r.photo) if r.photo else None,
            'matieres': r.liste_matieres, 'ville': r.ville, 'quartier': r.quartier, 'exemple': r.est_exemple}


def _actifs():
    from Repetiteurs.models import Repetiteur
    return Repetiteur.objects.filter(actif=True)


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(60)
def liste(request):
    qs = _actifs()
    tous = list(qs)
    q = (request.GET.get('q') or '').strip()
    if q:
        from .recherche import filtrer
        qs = filtrer(qs, q, 'nom', 'matieres', 'ville', 'quartier', 'niveaux')
    if request.GET.get('matiere'):
        qs = qs.filter(matieres__icontains=request.GET['matiere'])
    if request.GET.get('ville'):
        qs = qs.filter(ville__iexact=request.GET['ville'])
    matieres = sorted({m for r in tous for m in r.liste_matieres}, key=str.lower)
    villes = sorted({r.ville for r in tous if r.ville}, key=str.lower)
    return Response({'resultats': [item(request, r) for r in qs], 'matieres': matieres, 'villes': villes})


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(60)
def detail(request, pk):
    r = _actifs().filter(pk=pk).first()
    if not r:
        return error("Introuvable.", 404, code='introuvable')
    d = item(request, r)
    d.update({'photo_grande': grande(request, r.photo) if r.photo else None, 'niveaux': r.niveaux,
              'description': text(r.description), 'experience': r.experience, 'tarif': r.tarif,
              'whatsapp': ''.join(c for c in r.whatsapp if c.isdigit()), 'email': r.email, 'telephone': r.telephone,
              'latitude': float(r.latitude) if r.latitude is not None else None,
              'longitude': float(r.longitude) if r.longitude is not None else None})
    return Response(d)
