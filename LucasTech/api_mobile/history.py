"""Historique de l'utilisateur pour l'application : mêmes sources que la page web « Historique »
(core/history.py) — paiements en ligne de tous types, commandes boutique hors ligne, inscriptions
aux formations — mais avec des liens d'API (téléchargement authentifié) au lieu de liens web."""
from django.urls import reverse

from .utils import absolute, dt, media

TYPES = ('tous', 'boutique', 'formations', 'services', 'concours', 'tickets', 'paiements')
PAYMENT_TYPE = {'service': 'services', 'formation': 'formations', 'shop': 'boutique', 'product': 'boutique',
                'ticket': 'tickets', 'abonnement': 'concours', 'soutien': 'paiements'}
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
            'cle': f'paiement-{p.reference}', '_paiement': True,
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
            'cle': f'commande-{o.pk}', '_paiement': False,
        })
    if user.email:
        for r in Registration.objects.filter(email__iexact=user.email).select_related('formation'):
            out.append({
                'type': 'formations', 'titre': f"Inscription : {r.formation.title}", 'sous_titre': "Demande envoyée",
                'montant': None, 'devise': 'FCFA', 'statut': 'en_attente', 'statut_libelle': "Demande envoyée",
                'date': r.created_at, 'image': media(request, r.formation.image), 'lien_telechargement': None,
                'cle': f'inscription-{r.pk}', '_paiement': False,
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


def _masque(phone):
    d = ''.join(c for c in (phone or '') if c.isdigit())
    return ('•' * max(0, len(d) - 4) + d[-4:]) if d else ''


def detail(request, user, cle):
    """Fiche complète d'une ligne de l'historique (paiement, commande boutique, inscription)."""
    from Formations.models import Registration
    from Payments.models import Payment
    from Shop.models import ShopOrder

    kind, _, ident = (cle or '').partition('-')
    if kind == 'paiement':
        p = (Payment.objects.filter(reference=ident, user=user)
             .select_related('formation', 'service', 'event', 'product', 'shop_order').prefetch_related('tickets').first())
        if not p:
            return None
        t = PAYMENT_TYPE.get(p.kind, 'services')
        qty = sum(int(i.get('quantity') or 0) for i in (p.items or [])) or 1
        achat = None  # pour « Réessayer » : relancer le même achat dans l'appli
        if p.kind == 'formation' and p.formation_id:
            achat = {'type': 'formation', 'id': p.formation_id}
        elif p.kind == 'service' and p.service_id:
            achat = {'type': 'service', 'id': p.service_id}
        elif p.kind == 'product' and p.product_id:
            achat = {'type': 'produit', 'id': p.product_id, 'quantite': qty}
        elif p.kind == 'abonnement':
            sub = p.contest_subscriptions.select_related('plan').first()
            if sub:
                achat = {'type': 'abonnement', 'formule': sub.plan.code, 'periode': sub.period}
        elif p.kind == 'ticket' and p.event_id:
            achat = {'type': 'ticket', 'id': p.event_id}
        lien = (absolute(request, reverse('api_mobile:telechargement', args=[p.reference]))
                if p.is_paid and p.downloadable_file else None)
        return {
            'cle': cle, 'type': t, 'titre': p.description, 'image': _payment_image(request, p),
            'reference': p.reference, 'reference_fedapay': p.fedapay_id or '',
            'montant': p.amount, 'devise': 'FCFA', 'quantite': qty,
            'statut': PAYMENT_STATUS.get(p.status, 'en_attente'), 'statut_libelle': p.get_status_display(),
            'date': dt(p.created_at), 'paye_le': dt(p.paid_at), 'mis_a_jour': dt(p.updated_at),
            'moyen': 'Mobile Money' if p.operator else '', 'operateur': p.operator_short if p.operator else '',
            'telephone': _masque(p.phone), 'motif': p.failure_reason or '',
            'url_fedapay': p.payment_url if p.status == 'pending' else '',
            'lien_telechargement': lien, 'achat': achat,
            'tickets': [{'code': x.code, 'titulaire': x.holder_name} for x in p.tickets.all()] if p.kind == 'ticket' else [],
            'abonnement': p.kind == 'abonnement' and p.is_paid,
        }
    if kind == 'commande':
        o = ShopOrder.objects.filter(pk=ident if ident.isdigit() else 0, user=user).prefetch_related('items__product').first()
        if not o:
            return None
        items = [i for i in o.items.all() if i.product_id]
        return {
            'cle': cle, 'type': 'boutique', 'titre': ", ".join(f"{i.product.name} × {i.quantity}" for i in items)
            or f"Commande {o.receipt_number}", 'image': media(request, items[0].product.image) if items else None,
            'reference': o.receipt_number, 'reference_fedapay': '', 'montant': int(o.total_price), 'devise': 'FCFA',
            'quantite': sum(i.quantity for i in items) or 1, 'statut': ORDER_STATUS.get(o.status, 'en_attente'),
            'statut_libelle': o.get_status_display(), 'date': dt(o.created_at), 'paye_le': None, 'mis_a_jour': None,
            'moyen': o.get_payment_method_display(), 'operateur': '', 'telephone': _masque(o.cash_delivery_phone),
            'motif': '', 'url_fedapay': '', 'lien_telechargement': None, 'achat': None, 'tickets': [],
            'abonnement': False,
            'articles': [{'nom': i.product.name, 'quantite': i.quantity, 'prix': int(i.price)} for i in items],
        }
    if kind == 'inscription':
        r = Registration.objects.filter(pk=ident if ident.isdigit() else 0, email__iexact=user.email).select_related('formation').first()
        if not r:
            return None
        return {
            'cle': cle, 'type': 'formations', 'titre': f"Inscription : {r.formation.title}",
            'image': media(request, r.formation.image), 'reference': '', 'reference_fedapay': '', 'montant': None,
            'devise': 'FCFA', 'quantite': 1, 'statut': 'en_attente', 'statut_libelle': 'Demande envoyée',
            'date': dt(r.created_at), 'paye_le': None, 'mis_a_jour': None, 'moyen': '', 'operateur': '',
            'telephone': '', 'motif': '', 'url_fedapay': '', 'lien_telechargement': None,
            'achat': None, 'tickets': [], 'abonnement': False,
        }
    return None
