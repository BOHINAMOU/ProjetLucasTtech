"""Historique de l'utilisateur pour l'application : mêmes sources que la page web « Historique »
(core/history.py) — paiements en ligne de tous types, commandes boutique hors ligne, inscriptions
aux formations — mais avec des liens d'API (téléchargement authentifié) au lieu de liens web."""
from django.urls import reverse

from .utils import absolute, dt, media

TYPES = ('tous', 'boutique', 'formations', 'services', 'concours', 'tickets', 'paiements')
PAYMENT_TYPE = {'service': 'services', 'formation': 'formations', 'shop': 'boutique', 'product': 'boutique',
                'ticket': 'tickets', 'abonnement': 'concours'}
PAYMENT_STATUS = {'approved': 'paye', 'pending': 'en_attente', 'declined': 'refuse', 'canceled': 'annule'}
ORDER_STATUS = {'paid': 'paye', 'delivered': 'paye', 'shipped': 'paye', 'cancelled': 'annule'}


def _payment_image(request, p):
    if p.formation_id:
        return media(request, p.formation.image)
    if p.service_id:
        return media(request, p.service.image)
    if p.event_id:
        return media(request, p.event.cover)
    if p.product_id:
        return media(request, p.product.image)
    if p.shop_order_id:
        item = next((i for i in p.shop_order.items.all() if i.product_id), None)
        return media(request, item.product.image) if item else None
    return None


def entries(request, user):
    from Formations.models import Registration
    from Payments.models import Payment
    from Shop.models import ShopOrder

    out = []
    payments = (Payment.objects.filter(user=user)
                .select_related('formation', 'service', 'event', 'product', 'shop_order')
                .prefetch_related('shop_order__items__product', 'tickets'))
    for p in payments:
        t = PAYMENT_TYPE.get(p.kind, 'services')
        sous_titre = f"Réf. {p.reference}"
        if t == 'tickets':
            n = len(p.tickets.all())
            if n:
                sous_titre += f" · {n} ticket{'s' if n > 1 else ''}"
        lien = None
        if p.is_paid and p.downloadable_file:
            lien = absolute(request, reverse('api_mobile:telechargement', args=[p.reference]))
        out.append({
            'type': t, 'titre': p.description, 'sous_titre': sous_titre, 'montant': p.amount, 'devise': 'FCFA',
            'statut': PAYMENT_STATUS.get(p.status, 'en_attente'), 'statut_libelle': p.get_status_display(),
            'date': p.created_at, 'image': _payment_image(request, p), 'lien_telechargement': lien,
            '_paiement': True,
        })
    orders = ShopOrder.objects.filter(user=user).exclude(payment_method='fedapay').prefetch_related('items__product')
    for o in orders:
        items = [i for i in o.items.all() if i.product_id]
        names = ", ".join(f"{i.product.name} × {i.quantity}" for i in items)
        out.append({
            'type': 'boutique', 'titre': names or f"Commande {o.receipt_number}",
            'sous_titre': f"Commande {o.receipt_number} · {o.get_payment_method_display()}".strip(),
            'montant': int(o.total_price), 'devise': 'FCFA', 'statut': ORDER_STATUS.get(o.status, 'en_attente'),
            'statut_libelle': o.get_status_display(), 'date': o.created_at,
            'image': media(request, items[0].product.image) if items else None, 'lien_telechargement': None,
            '_paiement': False,
        })
    if user.email:
        for r in Registration.objects.filter(email__iexact=user.email).select_related('formation'):
            out.append({
                'type': 'formations', 'titre': f"Inscription : {r.formation.title}", 'sous_titre': "Demande envoyée",
                'montant': None, 'devise': 'FCFA', 'statut': 'en_attente', 'statut_libelle': "Demande envoyée",
                'date': r.created_at, 'image': media(request, r.formation.image), 'lien_telechargement': None,
                '_paiement': False,
            })
    out.sort(key=lambda e: e['date'], reverse=True)
    return out


def filtered(request, user, kind):
    kind = kind if kind in TYPES else 'tous'
    rows = entries(request, user)
    if kind == 'paiements':
        rows = [e for e in rows if e['_paiement']]
    elif kind != 'tous':
        rows = [e for e in rows if e['type'] == kind]
    for e in rows:
        e.pop('_paiement')
        e['date'] = dt(e['date'])
    return rows
