"""Événements dans l'admin : onglets En cours / À venir / Passés, et tableau de bord par événement."""
import csv
from datetime import timedelta

from django.contrib import admin as _admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone


def _f(n):
    return f"{int(n or 0):,} CFA".replace(',', ' ')


def statut(e):
    """(code, libellé) : brouillon, en cours, à venir, passé."""
    if not e.is_published:
        return 'brouillon', 'Brouillon'
    now = timezone.now()
    if e.starts_at and e.starts_at > now:
        return 'venir', 'À venir'
    if e.is_past:
        return 'passe', 'Passé'
    return 'cours', 'En cours'


def evenements_visibles(request):
    from Events.models import Event
    qs = Event.objects.all()
    if not request.user.is_superuser:
        from .delegations import evenements_visibles as ev
        qs = ev(request.user, qs)
    return qs


def onglets(request):
    """(onglets, vue, liste) pour la page de la rubrique Événements."""
    tous = list(evenements_visibles(request).order_by('-starts_at'))
    for e in tous:
        e.statut_code, e.statut = statut(e)
    groupes = {
        'cours': [e for e in tous if e.statut_code == 'cours'],
        'venir': sorted([e for e in tous if e.statut_code == 'venir'], key=lambda e: e.starts_at),
        'passe': [e for e in tous if e.statut_code == 'passe'],
        'brouillon': [e for e in tous if e.statut_code == 'brouillon'],
    }
    noms = [('cours', 'En cours'), ('venir', 'À venir'), ('passe', 'Passés'), ('brouillon', 'Brouillons')]
    vue = request.GET.get('vue') or next((c for c, _ in noms if groupes[c]), 'cours')
    if vue not in groupes:
        vue = 'cours'
    return [(c, n, len(groupes[c])) for c, n in noms], vue, groupes[vue]


def _evenement(request, pk):
    e = evenements_visibles(request).filter(pk=pk).first()
    if not e:
        raise Http404
    return e


@staff_member_required
def tableau(request, pk):
    e = _evenement(request, pk)
    e.statut_code, e.statut = statut(e)
    ok = e.payments.filter(status='approved')
    tickets = e.tickets.select_related('ticket_type')
    soutiens = ok.filter(kind='soutien')
    now = timezone.now()
    debut = (e.created_at or now) if (now - (e.created_at or now)).days < 60 else now - timedelta(days=60)
    jours = []
    j = timezone.localtime(debut).date()
    fin = timezone.localtime(now).date()
    while j <= fin:
        jours.append({'label': j.strftime('%d/%m'), 'v': ok.filter(paid_at__date=j).aggregate(s=Sum('amount'))['s'] or 0})
        j += timedelta(days=1)
    pic = max([x['v'] for x in jours] + [1])
    for x in jours:
        x['h'] = max(3, round(100 * x['v'] / pic)) if x['v'] else 3
        x['txt'] = _f(x['v'])
    par_type = []
    for tt in e.ticket_types.all() if hasattr(e, 'ticket_types') else []:
        n = tickets.filter(ticket_type=tt).count()
        par_type.append({'nom': tt.name, 'vendus': n, 'places': tt.quantity, 'prix': _f(tt.price)})
    ctx = dict(_admin.site.each_context(request), title=e.title, e=e, jours=jours, par_type=par_type,
               kpis=[
                   ("Encaissé", _f(ok.aggregate(s=Sum('amount'))['s'])),
                   ("Tickets vendus", tickets.count()),
                   ("Entrées validées", tickets.filter(used_at__isnull=False).count()),
                   ("Soutiens reçus", f"{soutiens.count()} · {_f(soutiens.aggregate(s=Sum('amount'))['s'])}"),
                   ("Paiements en attente", e.payments.filter(status='pending').count()),
               ],
               derniers=e.payments.order_by('-created_at')[:12],
               liens={
                   'modifier': reverse('admin:Events_event_change', args=[e.pk]),
                   'paiements': reverse('admin:Payments_payment_changelist') + f'?event__id__exact={e.pk}',
                   'tickets': reverse('admin:Events_ticket_changelist') + f'?event__id__exact={e.pk}',
                   'csv': reverse('admin_evenement_csv', args=[e.pk]),
                   'notifier': reverse('admin:api_mobile_notification_add') + f'?titre={e.title[:100]}',
                   'site': e.get_absolute_url(),
               })
    return render(request, 'admin/evenement.html', ctx)


@staff_member_required
def export_csv(request, pk):
    e = _evenement(request, pk)
    r = HttpResponse(content_type='text/csv; charset=utf-8')
    r['Content-Disposition'] = f'attachment; filename="evenement-{e.pk}.csv"'
    r.write('﻿')
    w = csv.writer(r, delimiter=';')
    w.writerow(['Référence', 'Date', 'Nom', 'Téléphone', 'Type', 'Montant (CFA)', 'Statut', 'Tickets'])
    for p in e.payments.order_by('created_at'):
        w.writerow([p.reference, timezone.localtime(p.created_at).strftime('%d/%m/%Y %H:%M'),
                    f"{p.first_name} {p.last_name}".strip(), p.phone, p.get_kind_display(), p.amount,
                    p.get_status_display(), p.tickets.count()])
    return r
