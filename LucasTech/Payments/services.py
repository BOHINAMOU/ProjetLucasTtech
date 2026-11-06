"""Cycle de vie d'un paiement : création chez FedaPay, vérification, livraison."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from . import fedapay
from .models import Payment

logger = logging.getLogger(__name__)


def start(request, payment):
    """Envoie le client vers la page de paiement (FedaPay ou démo). Renvoie l'URL ou lève FedaPayError."""
    payment.mode = fedapay.mode()
    if payment.mode == 'demo':
        payment.save()
        return reverse('payments:demo', args=[payment.reference]) + f'?t={payment.access_token}'
    callback = request.build_absolute_uri(reverse('payments:callback', args=[payment.reference]))
    tx_id, url = fedapay.create_transaction(payment, callback)
    payment.fedapay_id = tx_id
    payment.payment_url = url
    payment.save()
    return url


def refresh(payment):
    """Relit le statut chez FedaPay et livre si payé. Renvoie le paiement à jour."""
    if payment.status != 'pending' or not payment.fedapay_id or payment.mode == 'demo':
        return payment
    status = fedapay.transaction_status(payment.fedapay_id)
    if status in fedapay.PAID_STATUSES:
        mark_paid(payment)
    elif status in fedapay.FAILED_STATUSES:
        Payment.objects.filter(pk=payment.pk, status='pending').update(
            status='canceled' if status == 'canceled' else 'declined')
        _release(payment)
    payment.refresh_from_db()
    return payment


def mark_paid(payment):
    """Passe le paiement à « payé » et livre (une seule fois, même si webhook + retour arrivent ensemble)."""
    with transaction.atomic():
        p = Payment.objects.select_for_update().get(pk=payment.pk)
        if p.fulfilled:
            return p
        p.status = 'approved'
        p.paid_at = p.paid_at or timezone.now()
        _fulfill(p)
        p.fulfilled = True
        p.save()
    _send_confirmation(p)
    return p


def _fulfill(p):
    if p.kind == 'formation' and p.formation_id:
        from Formations.models import Formation, Order, OrderItem
        if p.user_id:
            order = Order.objects.create(user_id=p.user_id, total_price=p.amount, status='paid')
            OrderItem.objects.create(order=order, formation_id=p.formation_id, quantity=1, price=p.amount)
        Formation.objects.filter(pk=p.formation_id).update(students_count=F('students_count') + 1)
    elif p.kind == 'shop' and p.shop_order_id:
        from Shop.models import ShopOrder
        ShopOrder.objects.filter(pk=p.shop_order_id).update(status='paid', payment_method='fedapay')
    elif p.kind == 'ticket' and p.event_id:
        from Events.services import issue_tickets
        issue_tickets(p)


def _release(payment):
    """Paiement échoué : rien à rendre pour l'instant (les tickets ne sont émis qu'après paiement)."""
    return None


def _send_confirmation(p):
    try:
        site = getattr(settings, 'SITE_URL', '').rstrip('/') or 'https://lantantetechnologie.com'
        link = site + p.get_absolute_url()
        body = (f"Bonjour {p.first_name},\n\n"
                f"Nous avons bien reçu votre paiement de {p.amount:,} FCFA pour : {p.description}.\n"
                f"Référence : {p.reference}\n\n").replace(',', ' ')
        if p.kind == 'ticket':
            body += f"Vos tickets sont disponibles ici :\n{link}\n\n"
        elif p.downloadable_file:
            body += f"Téléchargez votre document ici (lien personnel) :\n{link}\n\n"
        else:
            body += f"Récapitulatif :\n{link}\n\nNotre équipe vous contacte très vite.\n\n"
        body += "Merci de votre confiance,\nL'équipe Lantante Technologie"
        send_mail(f"Paiement confirmé — {p.description}", body, settings.DEFAULT_FROM_EMAIL, [p.email],
                  fail_silently=True)
    except Exception:
        logger.exception('Confirmation email failed for %s', p.reference)
