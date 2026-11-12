"""Droits d'accès aux concours : LA règle centrale, utilisée partout (pages, lecteur, fichiers).

Droits d'un utilisateur = union de tous ses abonnements actifs (et de leurs extensions)."""
from django.utils import timezone

from .models import SubscriptionContest, UserSubscription


def active_subscriptions(user, now=None):
    if not user or not user.is_authenticated:
        return UserSubscription.objects.none()
    return UserSubscription.objects.filter(user=user).active(now)


def has_unlimited(user, now=None):
    return active_subscriptions(user, now).filter(is_unlimited=True).exists()


def accessible_contest_ids(user, now=None):
    """Ensemble des id de concours accessibles via les sélections des abonnements actifs
    (hors formule illimitée : voir has_unlimited)."""
    subs = active_subscriptions(user, now)
    return set(SubscriptionContest.objects.filter(subscription__in=subs).values_list('contest_id', flat=True))


def user_can_access(user, contest, now=None):
    """True si l'utilisateur a accès à TOUTES les épreuves payantes de ce concours."""
    if not user or not user.is_authenticated or contest is None:
        return False
    if user.is_staff:
        return True
    if getattr(contest, 'is_demo', False):
        return False  # concours de démonstration : lisibles par l'équipe seulement
    now = now or timezone.now()
    if has_unlimited(user, now):
        return True
    return SubscriptionContest.objects.filter(
        subscription__in=active_subscriptions(user, now), contest=contest).exists()


def can_view_paper(user, paper):
    """Lire un document (sujet ou corrigé) = être connecté ET avoir un abonnement actif couvrant
    son concours (ou être de l'équipe). Règle stricte : la case « gratuite » n'ouvre plus l'accès."""
    return user_can_access(user, paper.session.contest)
