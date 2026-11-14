import csv

from django.contrib import admin, messages
from django.contrib.admin.actions import delete_selected
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from . import services
from .models import Payment

PAYES = ('approved', 'refunded')  # lignes avec de l'argent : jamais supprimées, seulement marquées
COULEURS = {'approved': ('#0B7A4B', '#E3F5EC'), 'pending': ('#9A6700', '#FFF4D6'), 'declined': ('#B42318', '#FDECEA'),
            'canceled': ('#475569', '#EEF1F5'), 'refunded': ('#6D28D9', '#EEE7FD')}


def francs(n):
    return f"{int(n or 0):,} F".replace(',', '\u202f')


def badge_statut(p):
    fg, bg = COULEURS.get(p.status, ('#334155', '#EEF1F5'))
    return format_html('<span style="background:{};color:{};padding:3px 10px;border-radius:999px;font-weight:700;'
                       'font-size:12px;white-space:nowrap">{}</span>', bg, fg, p.get_status_display())


def export_csv(queryset, nom):
    r = HttpResponse(content_type='text/csv; charset=utf-8')
    r['Content-Disposition'] = f'attachment; filename="{nom}-{timezone.localdate():%Y-%m-%d}.csv"'
    r.write('\ufeff')  # accents corrects dans Excel
    w = csv.writer(r, delimiter=';')
    w.writerow(['Référence', 'Date', 'Prénom', 'Nom', 'Téléphone', 'WhatsApp', 'E-mail', 'Objet', 'Événement',
                'Détail', 'Montant (F)', 'Statut', 'Opérateur', 'Réf. FedaPay', 'Payé le'])
    for p in queryset.select_related('event'):
        detail = ', '.join(f"{i.get('name', '')} × {i.get('quantity', '')}" for i in (p.items or []) if isinstance(i, dict))
        w.writerow([p.reference, timezone.localtime(p.created_at).strftime('%d/%m/%Y %H:%M'), p.first_name, p.last_name,
                    p.phone, p.whatsapp, p.email, p.description, p.event.title if p.event_id else '', detail, p.amount,
                    p.get_status_display(), p.operator, p.fedapay_id,
                    timezone.localtime(p.paid_at).strftime('%d/%m/%Y %H:%M') if p.paid_at else ''])
    return r


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['reference', 'date', 'client', 'phone', 'description', 'montant', 'statut', 'operator']
    list_display_links = ['reference', 'client']
    list_filter = ['status', 'kind', ('event', admin.RelatedOnlyFieldListFilter), 'mode', 'created_at']
    search_fields = ['reference', 'description', 'first_name', 'last_name', 'email', 'phone', 'whatsapp', 'city',
                     'fedapay_id', 'event__title']
    readonly_fields = [f.name for f in Payment._meta.fields]
    date_hierarchy = 'created_at'
    list_per_page = 50
    actions = ['exporter_csv', 'supprimer_non_payes', 'marquer_rembourse', 'marquer_annule', 'verify_with_fedapay']
    change_list_template = 'admin/Payments/payment/change_list.html'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # Un paiement réussi ou remboursé reste dans l'historique (trace de l'argent).
        if obj is not None and obj.status in PAYES:
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        a = super().get_actions(request)
        a.pop('delete_selected', None)  # remplacée par « Supprimer (non payés seulement) »
        return a

    @admin.display(description="Date", ordering='created_at')
    def date(self, p):
        return timezone.localtime(p.created_at).strftime('%d/%m/%Y %H:%M')

    @admin.display(description="Client", ordering='last_name')
    def client(self, p):
        return f"{p.first_name} {p.last_name}".strip() or '—'

    @admin.display(description="Montant", ordering='amount')
    def montant(self, p):
        return francs(p.amount)

    @admin.display(description="Statut", ordering='status')
    def statut(self, p):
        return badge_statut(p)

    def changelist_view(self, request, extra_context=None):
        r = super().changelist_view(request, extra_context=extra_context)
        try:
            qs = r.context_data['cl'].queryset
            ok = qs.filter(status='approved')
            r.context_data['resume'] = {
                'encaisse': francs(ok.aggregate(s=Sum('amount'))['s']),
                'payeurs': ok.count(),
                'attente': qs.filter(status='pending').count(),
                'echecs': qs.filter(status__in=('declined', 'canceled')).count(),
                'rembourses': qs.filter(status='refunded').count(),
            }
        except (AttributeError, KeyError):
            pass
        return r

    @admin.action(description="Exporter en CSV (Excel)")
    def exporter_csv(self, request, queryset):
        return export_csv(queryset, 'paiements')

    @admin.action(description="Supprimer (non payés seulement)", permissions=['delete'])
    def supprimer_non_payes(self, request, queryset):
        garde = queryset.filter(status__in=PAYES).count()
        if garde and not request.POST.get('post'):
            self.message_user(request, f"{garde} paiement(s) payé(s) ou remboursé(s) ne seront pas supprimés.",
                              messages.WARNING)
        return delete_selected(self, request, queryset.exclude(status__in=PAYES))

    @admin.action(description="Marquer « Remboursé » (paiements réussis)")
    def marquer_rembourse(self, request, queryset):
        n = queryset.filter(status='approved').update(status='refunded')
        self.message_user(request, f"{n} paiement(s) marqué(s) remboursé(s).")

    @admin.action(description="Marquer « Annulé » (non payés)")
    def marquer_annule(self, request, queryset):
        n = queryset.filter(status__in=('pending', 'declined')).update(status='canceled')
        self.message_user(request, f"{n} paiement(s) annulé(s).")

    @admin.action(description="Revérifier le statut chez FedaPay")
    def verify_with_fedapay(self, request, queryset):
        for p in queryset.filter(status='pending'):
            services.refresh(p)
        messages.success(request, "Statuts revérifiés auprès de FedaPay.")
