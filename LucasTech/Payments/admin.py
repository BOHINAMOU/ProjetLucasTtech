from django.contrib import admin, messages

from . import services
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['reference', 'description', 'full_name', 'phone', 'whatsapp', 'city', 'operator', 'amount', 'status', 'mode', 'created_at']
    list_filter = ['status', 'kind', 'mode']
    search_fields = ['reference', 'description', 'first_name', 'last_name', 'email', 'phone', 'whatsapp', 'city', 'fedapay_id']
    readonly_fields = [f.name for f in Payment._meta.fields]
    actions = ['verify_with_fedapay']

    def has_add_permission(self, request):
        return False

    @admin.action(description="Revérifier le statut chez FedaPay")
    def verify_with_fedapay(self, request, queryset):
        for p in queryset.filter(status='pending'):
            services.refresh(p)
        messages.success(request, "Statuts revérifiés auprès de FedaPay.")
