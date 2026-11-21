"""Tuiles de l'accueil de l'appli (« Explorez nos services »), réglées dans l'admin."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import TuileAccueil


@api_view(['GET'])
@permission_classes([AllowAny])
def tuiles_accueil(request):
    """?plateforme=android|ios → tuiles affichées, dans l'ordre."""
    qs = TuileAccueil.objects.filter(active=True)
    plateforme = request.GET.get('plateforme')
    if plateforme == 'android':
        qs = qs.filter(android=True)
    elif plateforme == 'ios':
        qs = qs.filter(ios=True)
    return Response({'tuiles': [{'libelle': t.libelle, 'icone': t.icone, 'couleur': t.couleur,
                                 'destination': t.destination, 'url': t.url} for t in qs]})
