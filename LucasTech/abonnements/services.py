"""Règles métier des abonnements : achat, activation (après paiement FedaPay vérifié), extensions,
sélection des concours, expiration."""
import math
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .access import accessible_contest_ids, active_subscriptions, has_unlimited
from .models import (PERIOD_DAYS, ExtensionOption, SubscriptionContest, SubscriptionExtension,
                     SubscriptionPlan, UserSubscription)

MIN_PAYMENT = 100  # FCFA : en dessous, FedaPay refuse la transaction


class SelectionError(Exception):
    pass


# ─────────────────────────────────────────────
# Achat
# ─────────────────────────────────────────────
def create_pending_subscription(user, plan, period, payment=None):
    """Abonnement « en attente » : prix et limite FIGÉS maintenant. Aucun droit avant paiement."""
    period = period if period in PERIOD_DAYS else 'mois'
    return UserSubscription.objects.create(
        user=user, plan=plan, period=period, price_paid=plan.price_for(period),
        contest_limit=None if plan.is_unlimited else plan.contest_limit,
        is_unlimited=plan.is_unlimited, payment=payment)


def extension_price(option, subscription, now=None):
    """Prix d'une extension au prorata des jours restants de l'abonnement principal
    (base : prix pour 30 jours), arrondi aux 5 F supérieurs, minimum 100 F."""
    now = now or timezone.now()
    secs = max(0, (subscription.end_at - now).total_seconds()) if subscription.end_at else 0
    days = max(1, math.ceil(secs / 86400))
    raw = option.price * days / 30
    return max(MIN_PAYMENT, int(math.ceil(raw / 5) * 5))


def create_pending_extension(subscription, option, payment=None):
    if subscription.is_unlimited:
        raise SelectionError("Votre formule est déjà illimitée.")
    if not subscription.is_active:
        raise SelectionError("Cet abonnement n'est plus actif.")
    return SubscriptionExtension.objects.create(
        subscription=subscription, slots=option.slots, price_paid=extension_price(option, subscription),
        payment=payment)


def advice_for(user, plan):
    """Conseil automatique : 2e Standard -> Premium plus avantageux."""
    if plan.is_unlimited or not plan.contest_limit:
        return ''
    same = active_subscriptions(user).filter(plan=plan).count()
    if not same:
        return ''
    better = (SubscriptionPlan.objects.filter(is_active=True, is_unlimited=False,
                                              contest_limit__gt=(plan.contest_limit or 0) * 2,
                                              monthly_price__lte=plan.monthly_price * 2)
              .order_by('monthly_price').first())
    if not better:
        return ''
    return (f"Vous avez déjà {same} abonnement{'s' if same > 1 else ''} {plan.name}. "
            f"Le {better.name} est plus avantageux : {better.contest_limit} concours pour "
            f"{better.monthly_price:,} F au lieu de {plan.contest_limit * 2} concours pour "
            f"{plan.monthly_price * 2:,} F avec deux {plan.name}.").replace(',', ' ')


def ultimate_to_extend(user):
    return active_subscriptions(user).filter(is_unlimited=True).order_by('-end_at').first()


# ─────────────────────────────────────────────
# Activation (appelée UNIQUEMENT après paiement vérifié côté serveur)
# ─────────────────────────────────────────────
def activate_subscription(subscription_id, now=None):
    """Idempotent : une 2e confirmation ne fait rien. Ultimate déjà actif -> prolongation."""
    now = now or timezone.now()
    with transaction.atomic():
        sub = UserSubscription.objects.select_for_update().get(pk=subscription_id)
        if sub.status != 'en_attente':
            return sub
        delta = timedelta(days=PERIOD_DAYS.get(sub.period, 30))
        if sub.is_unlimited:
            current = (UserSubscription.objects.select_for_update()
                       .filter(user=sub.user, is_unlimited=True).exclude(pk=sub.pk).active(now)
                       .order_by('-end_at').first())
            if current:
                current.end_at = current.end_at + delta
                current.save(update_fields=['end_at'])
                sub.status = 'fusionne'
                sub.merged_into = current
                sub.start_at, sub.end_at, sub.activated_at = now, current.end_at, now
                sub.save()
                return sub
        sub.status = 'actif'
        sub.start_at, sub.end_at, sub.activated_at = now, now + delta, now
        sub.save()
        return sub


def activate_extension(extension_id, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        ext = SubscriptionExtension.objects.select_for_update().get(pk=extension_id)
        if ext.status != 'en_attente':
            return ext
        ext.status = 'actif'
        ext.activated_at = now
        ext.save()
        return ext


def fulfill_payment(payment):
    """Branché sur Payments.services._fulfill (kind='abonnement')."""
    for sub in UserSubscription.objects.filter(payment=payment, status='en_attente'):
        activate_subscription(sub.pk)
    for ext in SubscriptionExtension.objects.filter(payment=payment, status='en_attente'):
        activate_extension(ext.pk)


# ─────────────────────────────────────────────
# Sélection des concours
# ─────────────────────────────────────────────
def selection_states(user, subscription, contests):
    """Pour chaque concours : 'ici' (déjà dans cet abonnement), 'deja' (déjà accessible par un
    autre abonnement actif : non sélectionnable) ou 'libre'."""
    mine = set(subscription.contests.values_list('contest_id', flat=True))
    elsewhere = accessible_contest_ids(user) - mine
    unlimited = has_unlimited(user)
    out = []
    for c in contests:
        if c.pk in mine:
            state = 'ici'
        elif unlimited or c.pk in elsewhere:
            state = 'deja'
        else:
            state = 'libre'
        out.append((c, state))
    return out


def add_contests(subscription, contests):
    """Ajoute des concours à un abonnement actif (gratuit, dans la limite des places libres).
    Une sélection activée est définitive : on ne retire rien ici."""
    with transaction.atomic():
        sub = UserSubscription.objects.select_for_update().get(pk=subscription.pk)
        if not sub.is_active:
            raise SelectionError("Cet abonnement n'est pas actif.")
        if sub.is_unlimited:
            raise SelectionError("Votre formule donne déjà accès à tous les concours.")
        contests = list({c.pk: c for c in contests}.values())
        if not contests:
            raise SelectionError("Choisissez au moins un concours.")
        if any(not c.is_published for c in contests):
            raise SelectionError("Concours indisponible.")
        states = dict((c.pk, s) for c, s in selection_states(sub.user, sub, contests))
        dup = [c for c in contests if states[c.pk] != 'libre']
        if dup:
            raise SelectionError("Déjà accessible : " + ", ".join(c.acronym for c in dup)
                                 + ". Choisissez d'autres concours.")
        free = sub.free_slots
        if len(contests) > free:
            raise SelectionError(f"Il vous reste {free} place{'s' if free > 1 else ''} sur cet abonnement "
                                 f"({len(contests)} choisie{'s' if len(contests) > 1 else ''}). "
                                 "Ajoutez une extension ou un autre abonnement.")
        for c in contests:
            SubscriptionContest.objects.create(subscription=sub, contest=c)
        return sub


# ─────────────────────────────────────────────
# Expiration
# ─────────────────────────────────────────────
def expire_overdue(now=None):
    """Passe en « expiré » les abonnements (et leurs extensions) dont la date de fin est passée.
    Les droits sont déjà coupés à la volée (filtre sur end_at) ; ceci tient les statuts à jour."""
    now = now or timezone.now()
    ids = list(UserSubscription.objects.filter(status='actif', end_at__lte=now).values_list('pk', flat=True))
    if ids:
        UserSubscription.objects.filter(pk__in=ids).update(status='expire')
        SubscriptionExtension.objects.filter(subscription_id__in=ids, status='actif').update(status='expire')
    return len(ids)


def active_extension_options():
    return ExtensionOption.objects.filter(is_active=True)
