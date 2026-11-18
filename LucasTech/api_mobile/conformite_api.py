"""Appli : signaler un contenu, demander la suppression de son compte (exigences Google Play)."""
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core.conformite import creer_signalement, demander_suppression


@api_view(['POST'])
@permission_classes([AllowAny])
def signaler(request):
    s, err = creer_signalement(request, request.data)
    if not s:
        return Response({'detail': err}, status=400)
    return Response({'ok': True, 'message': "Merci, votre signalement a été envoyé à l'équipe."}, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def supprimer_compte(request):
    d = demander_suppression(request.user, request.user.email, (request.data.get('motif') or '')[:2000], origine='appli')
    return Response({'ok': True, 'message': "Demande reçue. Votre compte sera supprimé sous 30 jours.", 'id': d.pk}, status=201)
