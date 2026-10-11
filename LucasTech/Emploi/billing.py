"""Publications payantes : commande, paiement, validation par Lantante, mise en ligne.

Le paiement est aujourd'hui confirmé à la main par l'équipe (Flooz / T-Money). Chaque fonction est
isolée pour qu'un paiement en ligne (PayGate…) puisse appeler `confirm_payment` plus tard sans rien changer d'autre.
"""
from datetime import timedelta

from django.utils import timezone

from .models import FeedPost, PublicationOrder, ServicePlan
from .services import notify, notify_staff

ADMIN_ORDER_URL = "/lantanteAdminTech/Emploi/publicationorder/{}/change/"


def employer_is_exempt(employer):
    """Partenaire dont le contrat inclut les publications : rien à payer."""
    return bool(employer.publishing_free)


def _staff_alert(order, text):
    notify_staff(text, ADMIN_ORDER_URL.format(order.pk))


def _order_url(order):
    return f"/emploi/commandes/{order.pk}/"


# ── création ────────────────────────────────────────────────────────────────
def create_order(employer, plan, **content):
    """Crée la commande et la place à la bonne étape : devis, paiement ou validation."""
    exempt = employer_is_exempt(employer)
    amount = 0 if (exempt or plan.quote_only) else plan.price
    order = PublicationOrder.objects.create(employer=employer, plan=plan, amount=amount, **content)
    if plan.quote_only and not exempt:
        order.status = 'quote'
    elif amount == 0:
        order.status = 'in_review'
    else:
        order.status = 'awaiting_payment'
    order.save(update_fields=['status'])
    _sync_linked_status(order)
    if order.status == 'in_review':
        if exempt and employer.is_verified:
            approve_order(order)  # partenaire de confiance : mise en ligne directe
        else:
            _staff_alert(order, f"À valider : {order.plan.name} — {employer.company_name}")
    elif order.status == 'quote':
        _staff_alert(order, f"Devis à établir : {order.plan.name} — {employer.company_name}")
    else:
        _staff_alert(order, f"Commande en attente de paiement : {order.plan.name} ({order.amount_label}) — {employer.company_name}")
    return order


def _sync_linked_status(order):
    """Garde l'offre / la demande liées dans l'état de la commande."""
    offer, request = order.job_offer, order.staffing_request
    if offer:
        mapping = {
            'quote': 'awaiting_payment', 'awaiting_payment': 'awaiting_payment',
            'payment_declared': 'awaiting_payment', 'in_review': 'pending',
            'changes_requested': 'awaiting_payment', 'published': 'published',
            'refused': 'rejected', 'refunded': 'rejected', 'cancelled': 'rejected',
        }
        new = mapping.get(order.status)
        if new and offer.status not in ('filled', 'closed') and offer.status != new:
            offer.status = new
            offer.save(update_fields=['status', 'updated_at'])
    if request and order.status == 'in_review' and request.status == 'new':
        request.status = 'in_progress'
        request.save(update_fields=['status', 'updated_at'])


# ── devis ───────────────────────────────────────────────────────────────────
def send_quote(order, amount, message=''):
    order.amount = amount
    order.status = 'awaiting_payment'
    if message:
        order.review_message = message
    order.save()
    _sync_linked_status(order)
    notify(order.employer.user,
           f"Votre devis pour « {order.plan.name} » : {order.amount_label}."
           + (f"\n\n{message}" if message else "") + "\n\nVous pouvez payer depuis votre espace pour lancer la prestation.",
           _order_url(order))


# ── paiement ────────────────────────────────────────────────────────────────
def declare_payment(order, method, phone, reference):
    """L'entreprise a envoyé l'argent et indique sa référence de transaction."""
    order.payment_method = method
    order.payer_phone = phone
    order.payment_reference = reference
    order.status = 'payment_declared'
    order.save()
    _sync_linked_status(order)
    _staff_alert(order, f"Paiement à vérifier : {order.amount_label} ({order.get_payment_method_display()}, "
                        f"réf. {reference}) — {order.employer.company_name}")


def confirm_payment(order, by=None):
    """Lantante a bien reçu l'argent : reçu émis, la publication passe en validation."""
    if order.paid_at:
        return
    order.paid_at = timezone.now()
    order.receipt_number = f"REC-{order.paid_at:%y%m}-{order.pk:05d}"
    order.status = 'in_review'
    order.save()
    _sync_linked_status(order)
    notify(order.employer.user,
           f"Paiement confirmé ({order.amount_label}) pour « {order.plan.name} ». Merci ! "
           "Votre publication est en cours de validation par Lantante : patientez quelques instants. "
           f"Reçu n° {order.receipt_number}.", _order_url(order))
    _staff_alert(order, f"À valider (paiement confirmé) : {order.plan.name} — {order.employer.company_name}")


def payment_not_received(order, message=''):
    order.status = 'awaiting_payment'
    order.payment_reference = ''
    if message:
        order.review_message = message
    order.save()
    _sync_linked_status(order)
    notify(order.employer.user,
           "Nous n'avons pas retrouvé votre paiement pour « %s »." % order.plan.name
           + (f"\n\n{message}" if message else "")
           + "\n\nVérifiez la référence de la transaction puis renvoyez-la depuis votre espace.", _order_url(order))


# ── validation par l'équipe ─────────────────────────────────────────────────
def approve_order(order, by=None):
    """Met la publication en ligne."""
    if order.status == 'published':
        return
    now = timezone.now()
    plan = order.plan
    until = now + timedelta(days=plan.duration_days) if plan.duration_days else None
    if plan.kind in ('news', 'news_boost', 'ad'):
        post = order.feed_post or FeedPost(author=order.employer.user)
        post.text = (f"{order.title}\n\n{order.text}" if order.title else order.text).strip()
        post.kind = order.post_kind
        post.is_hidden = False
        post.is_featured = plan.kind in ('news_boost', 'ad')
        post.is_sponsored = plan.kind == 'ad'
        post.featured_until = until if post.is_featured else None
        if order.image:
            post.image = order.image
        post.save()
        order.feed_post = post
    elif plan.kind == 'job' and order.job_offer:
        offer = order.job_offer
        offer.status = 'published'
        offer.save(update_fields=['status', 'updated_at'])
    elif plan.kind == 'recruit' and order.staffing_request:
        request = order.staffing_request
        if request.status == 'new':
            request.status = 'in_progress'
            request.save(update_fields=['status', 'updated_at'])
    order.status = 'published'
    order.published_at = now
    order.visible_until = until
    order.save()
    notify(order.employer.user, f"Votre publication « {order.plan.name} » est validée et en ligne.", _order_url(order))


def request_changes(order, message):
    order.status = 'changes_requested'
    order.review_message = message
    order.save()
    _sync_linked_status(order)
    notify(order.employer.user,
           f"Votre publication « {order.plan.name} » demande une correction avant mise en ligne.\n\n{message}"
           "\n\nModifiez-la depuis votre espace puis renvoyez-la : votre paiement est conservé.", _order_url(order))


def refuse_order(order, message):
    order.status = 'refused'
    order.review_message = message
    order.save()
    _sync_linked_status(order)
    paid = " Votre paiement vous sera remboursé : Lantante vous contacte." if order.paid_at else ""
    notify(order.employer.user,
           f"Votre publication « {order.plan.name} » n'a pas pu être acceptée.\n\n{message}{paid}", _order_url(order))


def mark_refunded(order, note=''):
    order.status = 'refunded'
    if note:
        order.internal_note = (order.internal_note + "\n" + note).strip()
    order.save()
    _sync_linked_status(order)
    notify(order.employer.user, f"Votre paiement de {order.amount_label} pour « {order.plan.name} » a été remboursé.",
           _order_url(order))


def resubmit(order):
    """L'entreprise a corrigé : retour en validation (le paiement déjà effectué est conservé)."""
    if order.status == 'changes_requested':
        order.status = 'in_review' if order.paid_at or order.amount == 0 else 'awaiting_payment'
        order.save()
        _sync_linked_status(order)
        if order.status == 'in_review':
            _staff_alert(order, f"Publication corrigée à revalider : {order.plan.name} — {order.employer.company_name}")


def cancel_order(order):
    if order.status in ('awaiting_payment', 'quote'):
        order.status = 'cancelled'
        order.save()
        _sync_linked_status(order)
