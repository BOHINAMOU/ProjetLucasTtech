from django.contrib import admin

from .models import Event, Ticket, TicketType


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1
    fields = ['name', 'image', 'description', 'price', 'quantity', 'max_per_order', 'order', 'sold_display']
    readonly_fields = ['sold_display']

    @admin.display(description="Vendus")
    def sold_display(self, obj):
        return obj.sold if obj.pk else 0


class PaiementsInline(admin.TabularInline):
    """Participants (tickets) ou donateurs (soutien) de l'événement. Pour supprimer ou exporter :
    bouton « Gérer les paiements » (liste filtrée sur cet événement)."""
    from Payments.models import Payment as _P
    model = _P
    fk_name = 'event'
    extra = 0
    can_delete = False
    show_change_link = True
    verbose_name = "Paiement"
    verbose_name_plural = "Participants et donateurs"
    fields = ['quand', 'personne', 'phone', 'email', 'detail', 'montant_f', 'statut_c', 'fedapay_id']
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('-created_at')

    @admin.display(description="Date")
    def quand(self, p):
        from django.utils import timezone
        return timezone.localtime(p.created_at).strftime('%d/%m/%Y %H:%M')

    @admin.display(description="Nom")
    def personne(self, p):
        return f"{p.first_name} {p.last_name}".strip()

    @admin.display(description="Ticket × quantité")
    def detail(self, p):
        return ', '.join(f"{i.get('name', '')} × {i.get('quantity', '')}" for i in (p.items or []) if isinstance(i, dict)) or '—'

    @admin.display(description="Montant")
    def montant_f(self, p):
        from Payments.admin import francs
        return francs(p.amount)

    @admin.display(description="Statut")
    def statut_c(self, p):
        from Payments.admin import badge_statut
        return badge_statut(p)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'date_f', 'kind', 'payeurs', 'encaisse', 'is_published']
    list_filter = ['kind', 'is_published', 'organizer']
    readonly_fields = ['resume']
    date_hierarchy = 'starts_at'
    search_fields = ['title', 'location', 'description']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [TicketTypeInline, PaiementsInline]

    def get_queryset(self, request):
        from django.db.models import Count, Q, Sum
        qs = super().get_queryset(request).annotate(
            _payeurs=Count('payments', filter=Q(payments__status='approved')),
            _encaisse=Sum('payments__amount', filter=Q(payments__status='approved')))
        return qs if request.user.is_superuser else qs.filter(organizer=request.user)

    @admin.display(description="Date", ordering='starts_at')
    def date_f(self, obj):
        from django.utils import timezone
        return timezone.localtime(obj.starts_at).strftime('%d/%m/%Y %H:%M')

    @admin.display(description="Payeurs", ordering='_payeurs')
    def payeurs(self, obj):
        return obj._payeurs

    @admin.display(description="Encaissé", ordering='_encaisse')
    def encaisse(self, obj):
        from Payments.admin import francs
        return francs(obj._encaisse)

    @admin.display(description="Résumé")
    def resume(self, obj):
        from django.db.models import Sum
        from django.urls import reverse
        from django.utils.html import format_html
        from Payments.admin import francs
        if not obj.pk:
            return '—'
        ok = obj.payments.filter(status='approved')
        url = reverse('admin:Payments_payment_changelist') + f'?event__id__exact={obj.pk}'
        return format_html(
            '<b style="font-size:20px;color:#0B7A4B">{}</b> encaissés · <b>{}</b> personne(s) ont payé · {} en attente'
            '<br><a class="button" style="margin-top:8px;display:inline-block" href="{}">Gérer les paiements '
            '(filtrer, exporter, supprimer)</a>',
            francs(ok.aggregate(s=Sum('amount'))['s']), ok.count(), obj.payments.filter(status='pending').count(), url)
    list_editable = ['is_published']

    @admin.display(description="Tickets vendus")
    def tickets_sold(self, obj):
        return obj.tickets.count()

    @admin.display(description="Soutiens")
    def soutiens_display(self, obj):
        return obj.soutiens().count() if obj.is_soutien else '—'

    @admin.display(description="Collecté (FCFA)")
    def collecte_display(self, obj):
        from django.db.models import Sum
        return obj.soutiens().aggregate(s=Sum('amount'))['s'] or 0 if obj.is_soutien else '—'

    def get_readonly_fields(self, request, obj=None):
        # Seul l'administrateur attribue l'organisateur.
        return ['resume'] if request.user.is_superuser else ['resume', 'organizer']


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['code', 'event', 'ticket_type', 'holder_name', 'created_at', 'used_at']
    list_filter = ['event', 'ticket_type']
    search_fields = ['code', 'holder_name', 'payment__email', 'payment__phone']
    readonly_fields = ['code', 'event', 'ticket_type', 'payment', 'holder_name', 'created_at']

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('event', 'ticket_type')
        return qs if request.user.is_superuser else qs.filter(event__organizer=request.user)
