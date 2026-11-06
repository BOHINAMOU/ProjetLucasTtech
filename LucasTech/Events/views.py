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
from Payments.views import _remember, begin_payment, whatsapp_link

from .models import Event, Ticket, TicketType


def event_list(request):
    now = timezone.now()
    qs = Event.objects.filter(is_published=True).prefetch_related('ticket_types')
    upcoming = qs.filter(Q(ends_at__gte=now) | Q(ends_at__isnull=True, starts_at__gte=now))
    past = qs.exclude(pk__in=upcoming.values('pk')).order_by('-starts_at')[:6]
    return render(request, 'events/list.html', {'upcoming': upcoming, 'past': past})


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
    form = CustomerForm(request.POST or None, user=request.user)
    selected = {}
    if request.method == 'POST' and not event.is_past:
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
        'mode': fedapay.mode(),
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
        code = request.POST.get('code', '').strip().upper()
        ticket = Ticket.objects.filter(event=event, code=code).select_related('ticket_type').first()
        if not ticket:
            messages.error(request, f"Ticket {code} introuvable pour cet événement.")
        elif ticket.used_at:
            messages.error(request, f"Ticket {code} déjà validé le {timezone.localtime(ticket.used_at):%d/%m à %H:%M}.")
        else:
            ticket.used_at = timezone.now()
            ticket.save(update_fields=['used_at'])
            messages.success(request, f"✓ Ticket {code} valide ({ticket.ticket_type.name}, {ticket.holder_name}).")
        return redirect('events:organizer_event', slug=slug)

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
    })
