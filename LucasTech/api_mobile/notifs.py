"""Notifications dans l'appli : liste, compteur de non lues, lecture ; notifications automatiques."""
import logging

from django.db.models import Q
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Notification, NotificationLue
from .utils import dt

logger = logging.getLogger(__name__)


def pour(user):
    return Notification.objects.filter(
        Q(audience='tous') | Q(audience='personne', utilisateur=user) | Q(audience='groupe', groupe__in=user.groups.all())
    ).filter(created_at__gte=user.date_joined).distinct()


def notifier(user, titre, message, cible='', cible_id=None):
    """Notification automatique (paiement réussi, inscription…). Ne doit jamais faire échouer l'appelant."""
    if not user:
        return None
    try:
        return Notification.objects.create(titre=titre[:120], message=message[:600], audience='personne',
                                           utilisateur=user, cible=cible, cible_id=cible_id, automatique=True)
    except Exception:  # pragma: no cover
        logger.exception("Notification impossible")
        return None


def item(n, lues):
    return {'id': n.pk, 'titre': n.titre, 'message': n.message, 'date': dt(n.created_at), 'lue': n.pk in lues,
            'cible': n.cible, 'cible_id': n.cible_id, 'lien': n.lien}


@api_view(['GET'])
def liste(request):
    qs = list(pour(request.user)[:60])
    lues = set(NotificationLue.objects.filter(user=request.user, notification__in=qs).values_list('notification_id', flat=True))
    return Response({'non_lues': sum(1 for n in qs if n.pk not in lues), 'resultats': [item(n, lues) for n in qs]})


def non_lues(user):
    ids = list(pour(user).values_list('pk', flat=True))
    lues = NotificationLue.objects.filter(user=user, notification_id__in=ids).count()
    return max(0, len(ids) - lues)


@api_view(['GET'])
def compteur(request):
    return Response({'non_lues': non_lues(request.user)})


@api_view(['POST'])
def lire(request, pk=None):
    qs = pour(request.user)
    if pk:
        qs = qs.filter(pk=pk)
    for n in qs:
        NotificationLue.objects.get_or_create(notification=n, user=request.user)
    return Response({'non_lues': non_lues(request.user)})
