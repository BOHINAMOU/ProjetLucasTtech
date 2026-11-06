import json
import logging
import urllib.parse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import SiteSettings

from . import fedapay, mobile_money, services
from .forms import CustomerForm
from .models import Payment

logger = logging.getLogger(__name__)
SESSION_KEY = 'lt_payments'


# ─────────────────────────────────────────────
# Outils
# ─────────────────────────────────────────────
def whatsapp_link(text, number=None):
    number = number or SiteSettings.load().whatsapp_1
    if not number:
        return ''
    return f"https://wa.me/{number}?text={urllib.parse.quote(text)}"


def _remember(request, payment):
    refs = request.session.get(SESSION_KEY, [])
    if payment.reference not in refs:
        refs = (refs + [payment.reference])[-30:]
        request.session[SESSION_KEY] = refs


def _can_see(request, p):
    token = request.GET.get('t') or request.POST.get('t')
    if token and token == p.access_token:
        _remember(request, p)
        return True
    if p.reference in request.session.get(SESSION_KEY, []):
        return True
    u = request.user
    return u.is_authenticated and (u.is_staff or p.user_id == u.id)


def _get_visible(request, reference):
    p = get_object_or_404(Payment, reference=reference)
    if not _can_see(request, p):
        raise Http404
    return p


def begin_payment(request, form, **fields):
    """Crée le paiement à partir d'un CustomerForm valide et lance la demande Mobile Money.
    Renvoie une redirection, ou None si le paiement a été refusé (le message est ajouté au formulaire)."""
    sub = form.cleaned_data.get('submission') or ''
    done = request.session.get('lt_pay_submissions', {})
    if sub and sub in done:  # double clic / renvoi du formulaire : on ne crée pas un 2e paiement
        p = Payment.objects.filter(reference=done[sub]).first()
        if p:
            return redirect(p.get_absolute_url())
    user = form.create_account_if_asked()
    if user and not request.user.is_authenticated:
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    payment = Payment.objects.create(user=user, **form.payment_fields(), **fields)
    _remember(request, payment)
    try:
        url = services.start(request, payment)
    except fedapay.FedaPayError as exc:
        payment.status = 'canceled'
        payment.failure_reason = str(exc)[:255]
        payment.save(update_fields=['status', 'failure_reason'])
        form.add_error(None, str(exc))
        return None
    if sub:
        done[sub] = payment.reference
        request.session['lt_pay_submissions'] = dict(list(done.items())[-20:])
    return redirect(url)


# ─────────────────────────────────────────────
# Formulaire client (service / formation / commande boutique)
# ─────────────────────────────────────────────
def _target(request, kind, pk):
    """Renvoie (objet, montant, description, champs du paiement, url de retour)."""
    if kind == 'service':
        from Services.models import Service
        obj = get_object_or_404(Service, pk=pk, is_active=True)
        if not obj.price:
            raise Http404
        return obj, int(obj.price), f"Service : {obj.title}", {'kind': 'service', 'service': obj}, \
            obj.get_absolute_url()
    if kind == 'formation':
        from Formations.models import Formation
        obj = get_object_or_404(Formation, pk=pk, is_published=True, formation_type__in=('cours', 'numerique'))
        if not obj.price:
            raise Http404
        return obj, int(obj.price), f"Formation : {obj.title}", {'kind': 'formation', 'formation': obj}, \
            obj.get_absolute_url()
    if kind == 'produit':
        from Shop.models import Product
        obj = get_object_or_404(Product, pk=pk, is_available=True)
        try:
            qty = int(request.POST.get('qty') or request.GET.get('qty') or 1)
        except ValueError:
            qty = 1
        qty = max(1, min(qty, obj.stock or 1))
        unit = obj.bulk_price if (obj.bulk_price and qty >= obj.bulk_min_qty) else obj.price
        amount = int(unit) * qty
        desc = f"{obj.name} × {qty}" if qty > 1 else obj.name
        return obj, amount, desc, {'kind': 'product', 'product': obj,
                                   'items': [{'product': obj.pk, 'name': obj.name, 'quantity': qty,
                                              'price': int(unit)}]},             reverse('shop:product_detail', args=[obj.pk])
    if kind == 'boutique':
        from Shop.models import ShopOrder
        if not request.user.is_authenticated:
            raise Http404
        obj = get_object_or_404(ShopOrder, pk=pk, user=request.user, status='pending')
        return obj, int(obj.total_price), f"Commande boutique #{obj.receipt_number}", \
            {'kind': 'shop', 'shop_order': obj}, '/shop/historique/'
    raise Http404


def checkout(request, kind, pk):
    obj, amount, description, link_fields, back_url = _target(request, kind, pk)
    if kind == 'produit' and not obj.stock:
        raise Http404
    form = CustomerForm(request.POST or None, user=request.user, purpose=kind)
    if request.method == 'POST' and fedapay.is_enabled() and form.is_valid():
        response = begin_payment(request, form, amount=amount, description=description, **link_fields)
        if response:
            return response
    has_file = bool(getattr(obj, 'file', None))
    qty = link_fields.get('items', [{}])[0].get('quantity', 1) if kind == 'produit' else 1
    return render(request, 'payments/checkout.html', {
        'form': form, 'obj': obj, 'kind': kind, 'amount': amount, 'description': description, 'qty': qty,
        'back_url': back_url, 'has_file': has_file, 'enabled': fedapay.is_enabled(),
        'mode': fedapay.mode(), 'pay_js': pay_js_data(),
        'pay_label': f"Payer {amount:,} FCFA".replace(',', ' '),
        'whatsapp_url': whatsapp_link(f"Bonjour, je suis intéressé(e) par : {description} ({amount} FCFA)."),
    })


def pay_js_data():
    """Exemples de numéros et préfixes des opérateurs togolais, pour le formulaire (JS)."""
    return {
        'examples': {c: v['example'] for c, v in mobile_money.COUNTRIES.items()},
        'tg': {m: list(p) for m, (c, _l, p) in mobile_money.OPERATORS.items() if c == 'tg'},
    }


# ─────────────────────────────────────────────
# Retour FedaPay, résultat, téléchargement
# ─────────────────────────────────────────────
def callback(request, reference):
    p = get_object_or_404(Payment, reference=reference)
    services.refresh(p)
    if p.reference in request.session.get(SESSION_KEY, []) or (
            request.user.is_authenticated and p.user_id == request.user.id):
        return redirect(p.get_absolute_url())
    return redirect('payments:result', reference=p.reference)


def result(request, reference):
    p = _get_visible(request, reference)
    services.refresh(p)
    tickets = p.tickets.select_related('ticket_type') if p.kind == 'ticket' else []
    return render(request, 'payments/result.html', {
        'p': p, 'tickets': tickets, 'ussd': mobile_money.USSD.get(p.operator, ''),
        'direct': p.operator in mobile_money.DIRECT_MODES and not p.payment_url,
        'has_file': bool(p.downloadable_file),
        'auto_file': p.is_paid and bool(p.downloadable_file),
        'auto_receipt': p.is_paid and not p.downloadable_file,
        'whatsapp_url': whatsapp_link(f"Bonjour, paiement {p.reference} ({p.description})."),
    })


def status(request, reference):
    p = _get_visible(request, reference)
    if p.status == 'pending':
        services.refresh(p)
    return JsonResponse({'status': p.status})


def receipt(request, reference):
    """Reçu PDF d'un paiement réussi. ?telecharger=1 force le téléchargement."""
    from .receipt import build_receipt
    p = _get_visible(request, reference)
    if not p.is_paid:
        raise Http404
    resp = HttpResponse(build_receipt(p), content_type='application/pdf')
    mode = 'attachment' if request.GET.get('telecharger') else 'inline'
    resp['Content-Disposition'] = f'{mode}; filename="recu-{p.reference}.pdf"'
    resp['Cache-Control'] = 'private, no-store'
    return resp


def download(request, reference):
    p = _get_visible(request, reference)
    f = p.downloadable_file
    if not p.is_paid or not f:
        raise Http404
    name = f.name.rsplit('/', 1)[-1]
    return FileResponse(f.open('rb'), as_attachment=True, filename=name)


@csrf_exempt
@require_POST
def webhook(request):
    """FedaPay prévient ici des changements de statut. On ne croit pas le contenu :
    on relit le statut directement chez FedaPay avant de livrer quoi que ce soit."""
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except ValueError:
        return HttpResponseBadRequest('invalid json')
    entity = data.get('entity') or data.get('data') or {}
    tx_id = str(entity.get('id') or '')
    if tx_id:
        for p in Payment.objects.filter(fedapay_id=tx_id, status='pending'):
            services.refresh(p)
    return HttpResponse('ok')


# ─────────────────────────────────────────────
# Mode démo (local, sans clés FedaPay)
# ─────────────────────────────────────────────
def demo(request, reference):
    if fedapay.mode() != 'demo' or not settings.DEBUG:
        raise Http404
    p = _get_visible(request, reference)
    if request.method == 'POST' and p.status == 'pending':
        if request.POST.get('action') == 'pay':
            services.mark_paid(p)
        else:
            p.status = 'canceled'
            p.save(update_fields=['status'])
        return redirect(p.get_absolute_url())
    return render(request, 'payments/demo.html', {'p': p})
