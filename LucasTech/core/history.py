"""Page « Historique » : tout ce que l'utilisateur a fait sur le site, du plus récent au plus ancien
(paiements en ligne de tous types, commandes boutique hors ligne, inscriptions aux formations)."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

TYPES = [
    ('tout', 'Tout', 'fa-clock-rotate-left'),
    ('boutique', 'Boutique', 'fa-bag-shopping'),
    ('formations', 'Formations', 'fa-graduation-cap'),
    ('services', 'Services', 'fa-screwdriver-wrench'),
    ('concours', 'Concours', 'fa-file-pen'),
    ('evenements', 'Événements', 'fa-ticket'),
]
PAYMENT_TYPE = {'service': 'services', 'formation': 'formations', 'shop': 'boutique', 'product': 'boutique',
                'ticket': 'evenements', 'abonnement': 'concours'}
ICON = {k: icon for k, _l, icon in TYPES}
STATUS_CLASS = {'approved': 'ok', 'pending': 'wait', 'declined': 'ko', 'canceled': 'ko'}


def _entries(user):
    from Formations.models import Registration
    from Payments.models import Payment
    from Shop.models import ShopOrder

    out = []
    for p in Payment.objects.filter(user=user).select_related('formation', 'service', 'event'):
        t = PAYMENT_TYPE.get(p.kind, 'services')
        actions = [("Voir le reçu" if p.is_paid else "Voir", p.get_absolute_url(), 'fa-receipt')]
        if p.is_paid and p.downloadable_file:
            actions.insert(0, ("Télécharger le PDF",
                               reverse('payments:download', args=[p.reference]) + f'?t={p.access_token}', 'fa-download'))
        if t == 'concours' and p.is_paid:
            actions.insert(0, ("Mon espace concours", reverse('abonnements:space'), 'fa-graduation-cap'))
        out.append({'type': t, 'date': p.created_at, 'title': p.description, 'amount': p.amount,
                    'status': p.get_status_display(), 'status_class': STATUS_CLASS.get(p.status, 'wait'),
                    'ref': p.reference, 'actions': actions})
    for o in ShopOrder.objects.filter(user=user).exclude(payment_method='fedapay').prefetch_related('items__product'):
        names = ", ".join(f"{i.product.name} × {i.quantity}" for i in o.items.all() if i.product_id)
        out.append({'type': 'boutique', 'date': o.created_at, 'title': names or f"Commande {o.receipt_number}",
                    'amount': int(o.total_price), 'status': o.get_status_display(),
                    'status_class': 'ok' if o.status in ('paid', 'delivered', 'shipped') else
                    ('ko' if o.status == 'cancelled' else 'wait'),
                    'ref': o.receipt_number, 'actions': [("Mes commandes", reverse('shop:order_history'), 'fa-box')]})
    if user.email:
        for r in Registration.objects.filter(email__iexact=user.email).select_related('formation'):
            out.append({'type': 'formations', 'date': r.created_at, 'title': f"Inscription : {r.formation.title}",
                        'amount': None, 'status': "Demande envoyée", 'status_class': 'wait', 'ref': '',
                        'actions': [("Voir la formation", r.formation.get_absolute_url(), 'fa-eye')]})
    out.sort(key=lambda e: e['date'], reverse=True)
    for e in out:
        e['icon'] = ICON[e['type']]
    return out


@login_required
def history(request):
    entries = _entries(request.user)
    active = request.GET.get('type') or 'tout'
    if active not in ICON:
        active = 'tout'
    counts = {k: sum(1 for e in entries if k == 'tout' or e['type'] == k) for k in ICON}
    shown = [e for e in entries if active == 'tout' or e['type'] == active]
    return render(request, 'core/history.html', {
        'entries': shown, 'types': [(k, label, icon, counts[k]) for k, label, icon in TYPES], 'active': active,
    })
