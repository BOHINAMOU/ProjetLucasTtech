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
    """Lance le paiement et renvoie l'URL où envoyer le client :
    - paiement direct : la page d'attente du site (« Paiement en cours, validez sur votre téléphone ») ;
    - opérateur sans paiement direct : la page FedaPay ;
    - démo locale (sans clés) : la page de simulation. Lève FedaPayError en cas de refus."""
    payment.mode = fedapay.mode()
    payment.save(update_fields=['mode'])
    if payment.mode == 'demo':
        return reverse('payments:demo', args=[payment.reference]) + f'?t={payment.access_token}'
    callback = request.build_absolute_uri(reverse('payments:callback', args=[payment.reference]))
    url = fedapay.start(payment, callback)
    return url or payment.get_absolute_url()


def refresh(payment):
    """Relit le statut chez FedaPay et livre si payé. Renvoie le paiement à jour."""
    if payment.status != 'pending' or not payment.fedapay_id or payment.mode == 'demo':
        return payment
    status = fedapay.transaction_status(payment)
    if status in fedapay.PAID_STATUSES:
        mark_paid(payment)
    elif status in fedapay.FAILED_STATUSES:
        Payment.objects.filter(pk=payment.pk, status='pending').update(
            status='canceled' if status == 'canceled' else 'declined',
            failure_reason="Paiement non validé sur le téléphone. Rien n'a été débité.")
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
    elif p.kind == 'product' and p.product_id:
        from Shop.models import Product, ShopOrder, ShopOrderItem
        qty = sum(int(i.get('quantity') or 0) for i in p.items) or 1
        Product.objects.filter(pk=p.product_id, stock__gte=qty).update(stock=F('stock') - qty)
        if p.user_id:
            order = ShopOrder.objects.create(
                user_id=p.user_id, total_price=p.amount, status='paid', payment_method='fedapay',
                cash_delivery_name=p.full_name, cash_delivery_phone=p.whatsapp or p.phone,
                cash_delivery_message=p.address)
            ShopOrderItem.objects.create(order=order, product_id=p.product_id, quantity=qty,
                                         price=p.amount // qty)
    elif p.kind == 'ticket' and p.event_id:
        from Events.services import issue_tickets
        issue_tickets(p)


def _release(payment):
    """Paiement échoué : rien à rendre pour l'instant (les tickets ne sont émis qu'après paiement)."""
    return None


def _send_confirmation(p):
    if not p.email:
        return
    try:
        site = getattr(settings, 'SITE_URL', '').rstrip('/') or 'https://lantantetechnologie.com'
        link = site + p.get_absolute_url()
        body = (f"Bonjour {p.first_name},\n\n"
                f"Nous avons bien reçu votre paiement de {p.amount:,} FCFA pour : {p.description}.\n"
                f"Référence : {p.reference}\n\n").replace(',', ' ')
        if p.kind == 'ticket':
            body += (f"Votre reçu et vos tickets :\n{link}\n\n"
                     "L'organisateur vous appellera pour la livraison des tickets. Le jour J, présentez ce reçu "
                     "ou donnez votre nom à l'entrée.\n\n")
        elif p.kind in ('product', 'shop'):
            body += f"Votre reçu :\n{link}\n\nNous vous appelons très vite pour la livraison.\n\n"
        elif p.downloadable_file:
            body += f"Téléchargez votre document ici (lien personnel) :\n{link}\n\n"
        else:
            body += f"Récapitulatif :\n{link}\n\nNotre équipe vous contacte très vite.\n\n"
        body += "Merci de votre confiance,\nL'équipe Lantante Technologie"
        send_mail(f"Paiement confirmé — {p.description}", body, settings.DEFAULT_FROM_EMAIL, [p.email],
                  fail_silently=True)
    except Exception:
        logger.exception('Confirmation email failed for %s', p.reference)
