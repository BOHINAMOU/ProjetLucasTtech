from django.contrib import admin
from .models import ServiceCategory, Service, ServiceContact


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'icon', 'order']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'name']


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display  = ['title', 'admin', 'category', 'is_featured', 'is_active', 'created_at']
    list_filter   = ['is_active', 'is_featured', 'category']
    search_fields = ['title', 'description']
    list_editable = ['is_featured', 'is_active']

    def get_queryset(self, request):
        # Tout admin ayant accès à ce module voit tous les services
        # (et pas seulement les siens).
        return super().get_queryset(request)

    def save_model(self, request, obj, form, change):
        # Assigne automatiquement l'admin connecté si pas de superuser
        if not obj.pk and not request.user.is_superuser:
            obj.admin = request.user
        super().save_model(request, obj, form, change)


@admin.register(ServiceContact)
class ServiceContactAdmin(admin.ModelAdmin):
    list_display  = ['name', 'phone', 'service', 'created_at', 'is_read']
    list_filter   = ['is_read', 'service']
    list_editable = ['is_read']
    readonly_fields = ['name', 'phone', 'message', 'service', 'user', 'created_at']