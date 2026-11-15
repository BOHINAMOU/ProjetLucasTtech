"""Abonnement « Accès Épreuves » (1 an par défaut) : calcul de la fin, prolongation idempotente."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone


def fin_acces(user, now=None):
    """Date de fin de l'accès en cours (None si aucun accès actif)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    from .models import AccesEpreuves
    now = now or timezone.now()
    qs = AccesEpreuves.objects.filter(user=user, fin__gt=now)
    if not qs.filter(debut__lte=now).exists():
        return None
    return qs.order_by('-fin').values_list('fin', flat=True).first()


def actif(user, now=None):
    return fin_acces(user, now) is not None


def prolonger(payment):
    """Livraison d'un paiement « acces » réussi : ajoute une période, UNE seule fois par paiement."""
    from django.contrib.auth import get_user_model
    from .models import AccesEpreuves, ReglageAcces
    if not payment.user_id:
        return None
    with transaction.atomic():
        get_user_model().objects.select_for_update().filter(pk=payment.user_id).first()  # sérialise par client
        if AccesEpreuves.objects.filter(payment=payment).exists():
            return None
        now = timezone.now()
        derniere = AccesEpreuves.objects.filter(user_id=payment.user_id, fin__gt=now).order_by('-fin').first()
        debut = derniere.fin if derniere else now
        duree = ReglageAcces.load().duree_jours
        return AccesEpreuves.objects.create(user_id=payment.user_id, debut=debut, fin=debut + timedelta(days=duree),
                                            prix_paye=int(payment.amount) + int(payment.remise or 0), payment=payment)
