"""Boost des candidats : visibilité seulement. Il ne garantit ni présélection, ni entretien, ni recrutement.

Même mécanique de paiement que les publications des entreprises (Flooz / T-Money confirmé par Lantante) ;
`confirm_boost_payment` est le point d'entrée d'un futur paiement en ligne.
"""
from datetime import timedelta

from django.utils import timezone

from .models import BoostOrder
from .services import notify, notify_staff

TRANSPARENCY = ("Le boost augmente la visibilité de votre profil ou de votre candidature auprès des recruteurs. "
                "Il ne garantit ni une présélection, ni un entretien, ni un recrutement.")


def _url(boost):
    return f"/emploi/boosts/{boost.pk}/"


def _admin_url(boost):
    return f"/lantanteAdminTech/Emploi/boostorder/{boost.pk}/change/"


def create_boost(candidate, plan, application=None):
    boost = BoostOrder.objects.create(candidate=candidate, plan=plan, application=application, amount=plan.price,
                                      status='awaiting_payment')
    if plan.price == 0:
        confirm_boost_payment(boost)
    else:
        notify_staff(f"Boost en attente de paiement : {plan.name} ({boost.amount_label}) — {candidate.name}",
                     _admin_url(boost))
    return boost


def declare_boost_payment(boost, method, phone, reference):
    boost.payment_method = method
    boost.payer_phone = phone
    boost.payment_reference = reference
    boost.status = 'payment_declared'
    boost.save()
    notify_staff(f"Paiement de boost à vérifier : {boost.amount_label} ({boost.get_payment_method_display()}, "
                 f"réf. {reference}) — {boost.candidate.name}", _admin_url(boost))


def confirm_boost_payment(boost, by=None):
    """Paiement reçu : le boost démarre. Un boost acheté pendant un autre boost actif se place à la suite."""
    if boost.status == 'active':
        return
    now = timezone.now()
    base = now
    previous = BoostOrder.objects.filter(candidate=boost.candidate, application=boost.application, status='active',
                                         expires_at__gt=now).exclude(pk=boost.pk).order_by('-expires_at').first()
    if previous:
        base = previous.expires_at
    boost.paid_at = boost.paid_at or now
    boost.receipt_number = boost.receipt_number or f"REC-B{boost.paid_at:%y%m}-{boost.pk:05d}"
    boost.starts_at = base
    boost.expires_at = base + timedelta(days=boost.plan.duration_days or 30)
    boost.status = 'active'
    boost.save()
    target = "votre candidature" if boost.application_id else "votre profil"
    notify(boost.candidate.user,
           f"Paiement confirmé ({boost.amount_label}) : {target} est boosté jusqu'au {boost.expires_at:%d/%m/%Y}. "
           f"Merci de contribuer au développement de la plateforme !\n\n{TRANSPARENCY}\n\nReçu n° {boost.receipt_number}.",
           _url(boost))


def boost_payment_not_received(boost, message=''):
    boost.status = 'awaiting_payment'
    boost.payment_reference = ''
    boost.save()
    notify(boost.candidate.user,
           "Nous n'avons pas retrouvé votre paiement de boost." + (f"\n\n{message}" if message else "")
           + "\n\nVérifiez la référence puis renvoyez-la depuis votre espace.", _url(boost))


def refund_boost(boost, note=''):
    boost.status = 'refunded'
    boost.expires_at = timezone.now() if boost.expires_at else None
    if note:
        boost.internal_note = (boost.internal_note + "\n" + note).strip()
    boost.save()
    notify(boost.candidate.user, f"Votre paiement de {boost.amount_label} pour « {boost.plan.name} » a été remboursé.",
           _url(boost))


def cancel_boost(boost):
    if boost.status == 'awaiting_payment':
        boost.status = 'cancelled'
        boost.save()
