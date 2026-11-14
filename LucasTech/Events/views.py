from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from Payments import fedapay, services as pay_services
from Payments.forms import CustomerForm
from Payments.models import Payment
from Payments.views import _remember, begin_payment, pay_js_data, whatsapp_link

from .models import Event, Ticket, TicketType, a_venir_q


def event_list(request):
    now = timezone.now()
    qs = Event.objects.filter(is_published=True).prefetch_related('ticket_types')
    typ = request.GET.get('type') if request.GET.get('type') in ('tickets', 'soutien') else ''
    q = (request.GET.get('q') or '').strip()[:80]
    if typ:
        qs = qs.filter(kind=typ)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(location__icontains=q))
    upcoming = qs.filter(a_venir_q(now))
    past = qs.exclude(pk__in=upcoming.values('pk')).order_by('-starts_at')[:6]
    return render(request, 'events/list.html', {'upcoming': upcoming, 'past': past, 'type': typ, 'q': q})


def _selection(request, event):
    """Lit les quantités demandées : [(type, quantité)] ou lève ValueError avec un message."""
    chosen = []
    for tt in event.ticket_types.all():
        try:
            qty = int(request.POST.get(f'qty_{tt.pk}', 0) or 0)
        except ValueError:
            qty = 0
        if qty <= 0:
            continue
        if qty > tt.max_per_order:
            raise ValueError(f"« {tt.name} » : {tt.max_per_order} tickets maximum par commande.")
        if qty > tt.remaining:
            raise ValueError(f"« {tt.name} » : il ne reste que {tt.remaining} place(s).")
        chosen.append((tt, qty))
    if not chosen:
        raise ValueError("Choisissez au moins un ticket.")
    return chosen


def event_detail(request, slug):
    event = get_object_or_404(Event.objects.prefetch_related('ticket_types'), slug=slug, is_published=True)
    form = CustomerForm(request.POST or None, user=request.user, purpose='ticket')
    selected = {}
    if request.method == 'POST' and not event.is_past and event.is_soutien:
        try:
            montant = int(str(request.POST.get('montant') or '0').replace(' ', ''))
        except ValueError:
            montant = 0
        if montant < event.min_amount:
            messages.error(request, f"Montant minimal : {event.min_amount} FCFA.")
        elif form.is_valid() and fedapay.is_enabled():
            response = begin_payment(request, form, kind='soutien', event=event, amount=montant,
                                     description=f"Soutien : {event.title}")
            if response:
                return response
    elif request.method == 'POST' and not event.is_past:
        selected = {k[4:]: v for k, v in request.POST.items() if k.startswith('qty_')}
        try:
            with transaction.atomic():
                list(TicketType.objects.select_for_update().filter(event=event))  # verrou anti-survente
                chosen = _selection(request, event)
        except ValueError as e:
            messages.error(request, str(e))
            chosen = None
        if chosen and form.is_valid():
            items = [{'ticket_type': tt.pk, 'name': tt.name, 'quantity': q, 'price': tt.price} for tt, q in chosen]
            amount = sum(tt.price * q for tt, q in chosen)
            count = sum(q for _, q in chosen)
            desc = f"{count} ticket{'s' if count > 1 else ''} — {event.title}"
            if amount == 0:
                # Tickets gratuits : pas de passage par FedaPay.
                user = form.create_account_if_asked()
                p = Payment.objects.create(user=user, kind='ticket', event=event, items=items, amount=0,
                                           description=desc, mode='free', **form.payment_fields())
                _remember(request, p)
                pay_services.mark_paid(p)
                return redirect(p.get_absolute_url())
            if fedapay.is_enabled():
                response = begin_payment(request, form, kind='ticket', event=event, items=items,
                                         amount=amount, description=desc)
                if response:
                    return response
    return render(request, 'events/detail.html', {
        'event': event, 'form': form, 'selected': selected, 'enabled': fedapay.is_enabled(),
        'mode': fedapay.mode(), 'pay_js': pay_js_data(), 'montants': [500, 1000, 2000, 5000],
        'nb_soutiens': event.soutiens().count() if event.is_soutien else 0,
        'whatsapp_url': whatsapp_link(f"Bonjour, je souhaite des tickets pour « {event.title} »."),
    })


# ─────────────────────────────────────────────
# Espace organisateur : uniquement SES événements
# ─────────────────────────────────────────────
def _my_events(user):
    qs = Event.objects.all()
    return qs if user.is_superuser else qs.filter(organizer=user)


@login_required
def organizer_home(request):
    events = _my_events(request.user).annotate(
        sold=Count('tickets', distinct=True),
    ).order_by('-starts_at')
    rows = []
    for ev in events:
        revenue = Payment.objects.filter(event=ev, status='approved').aggregate(s=Sum('amount'))['s'] or 0
        rows.append((ev, revenue))
    if not rows and not request.user.is_superuser:
        messages.info(request, "Aucun événement ne vous est attribué pour l'instant.")
    return render(request, 'events/organizer_home.html', {'rows': rows})


@login_required
def organizer_event(request, slug):
    event = get_object_or_404(_my_events(request.user), slug=slug)
    if request.method == 'POST':
        ticket = Ticket.objects.filter(event=event, pk=request.POST.get('ticket')).select_related('ticket_type').first()
        if not ticket:
            messages.error(request, "Ticket introuvable pour cet événement.")
        elif ticket.used_at:
            messages.error(request, f"Ticket {ticket.code} déjà utilisé le {timezone.localtime(ticket.used_at):%d/%m à %H:%M}.")
        else:
            ticket.used_at = timezone.now()
            ticket.save(update_fields=['used_at'])
            messages.success(request, f"✓ Entrée validée : {ticket.holder_name} ({ticket.ticket_type.name}, {ticket.code}).")
        return redirect(request.get_full_path())

    # Recherche à l'entrée : nom, numéro de téléphone / WhatsApp, code du ticket ou référence du reçu
    q = request.GET.get('q', '').strip()
    found = []
    if q:
        digits = ''.join(c for c in q if c.isdigit())
        cond = (Q(code__iexact=q) | Q(holder_name__icontains=q) | Q(payment__reference__iexact=q)
                | Q(payment__first_name__icontains=q) | Q(payment__last_name__icontains=q))
        if len(digits) >= 6:
            cond |= Q(payment__phone__contains=digits[-8:]) | Q(payment__whatsapp__contains=digits[-8:])
        found = event.tickets.filter(cond).select_related('ticket_type', 'payment').order_by('holder_name', 'code')[:50]

    types = []
    for tt in event.ticket_types.all():
        sold = tt.tickets.count()
        types.append({'tt': tt, 'sold': sold, 'revenue': sold * tt.price,
                      'left': max(0, tt.quantity - sold)})
    payments = Payment.objects.filter(event=event, status='approved').prefetch_related('tickets')
    return render(request, 'events/organizer_event.html', {
        'event': event, 'types': types, 'payments': payments,
        'revenue': sum(t['revenue'] for t in types), 'sold': sum(t['sold'] for t in types),
        'used': event.tickets.filter(used_at__isnull=False).count(),
        'q': q, 'found': found,
    })
