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


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'starts_at', 'location', 'organizer', 'tickets_sold', 'is_published']
    list_filter = ['is_published', 'organizer']
    search_fields = ['title', 'location', 'description']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [TicketTypeInline]
    list_editable = ['is_published']

    @admin.display(description="Tickets vendus")
    def tickets_sold(self, obj):
        return obj.tickets.count()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(organizer=request.user)

    def get_readonly_fields(self, request, obj=None):
        # Seul l'administrateur attribue l'organisateur.
        return [] if request.user.is_superuser else ['organizer']


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
