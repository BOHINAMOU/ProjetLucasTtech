"""Page « Historique » : tout ce que l'utilisateur a fait sur le site, du plus récent au plus ancien
(paiements en ligne de tous types, commandes boutique hors ligne, inscriptions aux formations).
Les tentatives de paiement annulées / refusées sont masquées par défaut."""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

TYPES = [
    ('tout', 'Tout', 'fa-layer-group'),
    ('boutique', 'Boutique', 'fa-bag-shopping'),
    ('formations', 'Formations', 'fa-graduation-cap'),
    ('services', 'Services', 'fa-screwdriver-wrench'),
    ('concours', 'Concours', 'fa-file-pen'),
    ('evenements', 'Événements', 'fa-ticket'),
]
PAYMENT_TYPE = {'service': 'services', 'formation': 'formations', 'shop': 'boutique', 'product': 'boutique',
                'ticket': 'evenements', 'abonnement': 'concours'}
ICON = {k: icon for k, _l, icon in TYPES}
STATUS = {'approved': ('Payé', 'ok'), 'pending': ('En attente', 'wait'), 'declined': ('Refusé', 'ko'),
          'canceled': ('Annulé', 'ko')}


def _img(*fields):
    for f in fields:
        if f:
            try:
                return f.url
            except ValueError:
                continue
    return ''


def _entries(user):
    from Formations.models import Registration
    from Payments.models import Payment
    from Shop.models import ShopOrder

    out = []
    pays = Payment.objects.filter(user=user).select_related('formation', 'service', 'event', 'product', 'shop_order')
    for p in pays:
        t = PAYMENT_TYPE.get(p.kind, 'services')
        label, cls = STATUS.get(p.status, ('En attente', 'wait'))
        image = _img(getattr(p.product, 'image', None), getattr(p.formation, 'image', None),
                     getattr(p.service, 'image', None), getattr(p.event, 'cover', None))
        if not image and p.shop_order_id:
            first = p.shop_order.items.select_related('product').first()
            image = _img(getattr(getattr(first, 'product', None), 'image', None))
        extra = None
        if p.is_paid and p.downloadable_file:
            extra = (reverse('payments:download', args=[p.reference]) + f'?t={p.access_token}', 'fa-download',
                     'Télécharger le PDF')
        url = reverse('abonnements:space') if (t == 'concours' and p.is_paid) else p.get_absolute_url()
        out.append({'type': t, 'date': p.created_at, 'title': p.description, 'amount': p.amount,
                    'status': label, 'cls': cls, 'ref': p.reference, 'url': url, 'image': image, 'extra': extra,
                    'failed': p.status in ('declined', 'canceled')})
    for o in ShopOrder.objects.filter(user=user).exclude(payment_method='fedapay').prefetch_related('items__product'):
        items = [i for i in o.items.all() if i.product_id]
        names = ", ".join(f"{i.product.name}" + (f" × {i.quantity}" if i.quantity > 1 else "") for i in items)
        ok = o.status in ('paid', 'delivered', 'shipped', 'cash_on_delivery')
        out.append({'type': 'boutique', 'date': o.created_at, 'title': names or f"Commande {o.receipt_number}",
                    'amount': int(o.total_price), 'status': o.get_status_display(),
                    'cls': 'ok' if ok else ('ko' if o.status == 'cancelled' else 'wait'),
                    'ref': o.receipt_number, 'url': reverse('shop:order_history'), 'extra': None,
                    'image': _img(*(i.product.image for i in items)), 'failed': o.status == 'cancelled'})
    if user.email:
        for r in Registration.objects.filter(email__iexact=user.email).select_related('formation'):
            out.append({'type': 'formations', 'date': r.created_at, 'title': f"Inscription : {r.formation.title}",
                        'amount': None, 'status': "Inscription envoyée", 'cls': 'wait', 'ref': '',
                        'url': r.formation.get_absolute_url(), 'image': _img(r.formation.image), 'extra': None,
                        'failed': False})
    out.sort(key=lambda e: e['date'], reverse=True)
    for e in out:
        e['icon'] = ICON[e['type']]
    return out


def _day_label(d, today):
    if d == today:
        return "Aujourd'hui"
    if d == today - timedelta(days=1):
        return "Hier"
    fmt = "l j F" if d.year == today.year else "l j F Y"
    return date_format(d, fmt).capitalize()


@login_required
def history(request):
    entries = _entries(request.user)
    active = request.GET.get('type') or 'tout'
    if active not in ICON:
        active = 'tout'
    show_failed = request.GET.get('annules') == '1'
    in_type = [e for e in entries if active == 'tout' or e['type'] == active]
    hidden = sum(1 for e in in_type if e['failed'])
    shown = in_type if show_failed else [e for e in in_type if not e['failed']]

    today = timezone.localdate()
    groups = []
    for e in shown:
        d = timezone.localtime(e['date']).date()
        if not groups or groups[-1]['date'] != d:
            groups.append({'date': d, 'label': _day_label(d, today), 'items': []})
        groups[-1]['items'].append(e)

    paid = [e for e in entries if e['cls'] == 'ok' and e['amount']]
    counts = {k: sum(1 for e in entries if not e['failed'] and (k == 'tout' or e['type'] == k)) for k in ICON}
    return render(request, 'core/history.html', {
        'groups': groups, 'active': active, 'show_failed': show_failed, 'hidden': hidden,
        'types': [(k, label, icon, counts[k]) for k, label, icon in TYPES if k == 'tout' or counts[k]],
        'n_paid': len(paid), 'total_paid': sum(e['amount'] for e in paid),
    })
