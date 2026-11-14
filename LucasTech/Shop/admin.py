# Fichier : Shop/admin.py
from django.contrib import admin
from .models import (
    Announcement, CollabBanner, Category, Product, ProductImage,
    ShopOrder, ShopOrderItem, Reservation, Review,
)


class ProductImageInline(admin.TabularInline):
    model  = ProductImage
    extra  = 3
    fields = ['image', 'order']

class ShopOrderItemInline(admin.TabularInline):
    model = ShopOrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price') # Non-éditable ici

@admin.register(ShopOrder)
class ShopOrderAdmin(admin.ModelAdmin):
    # Les champs affichés correspondent maintenant au modèle
    list_display = ('receipt_number', 'user', 'montant', 'status', 'payment_method', 'date')
    date_hierarchy = 'created_at'

    @admin.display(description="Montant", ordering='total_price')
    def montant(self, obj):
        from Payments.admin import francs
        return francs(obj.total_price)

    @admin.display(description="Date", ordering='created_at')
    def date(self, obj):
        from django.utils import timezone
        return timezone.localtime(obj.created_at).strftime('%d/%m/%Y %H:%M')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('receipt_number', 'user__email')
    inlines = [ShopOrderItemInline]

# Enregistrement des autres modèles pour que l'admin fonctionne
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'old_price', 'stock', 'is_available', 'is_featured')
    list_filter = ('category', 'is_available', 'is_featured')
    search_fields = ('name', 'short_description', 'description')
    inlines = [ProductImageInline]
    fieldsets = (
        (None, {'fields': ('category', 'name', 'short_description', 'description')}),
        ('Prix', {'fields': ('price', 'old_price', 'bulk_price', 'bulk_min_qty')}),
        ('Photos et vidéo', {'fields': ('image', 'video')}),
        ('Stock et affichage', {'fields': ('stock', 'is_available', 'is_featured', 'contact_whatsapp')}),
    )

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'product', 'status', 'created_at')
    list_filter = ('status',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating',)

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('message', 'is_active', 'created_at')
    list_editable = ('is_active',)

@admin.register(CollabBanner)
class CollabBannerAdmin(admin.ModelAdmin):
    list_display = ('message', 'whatsapp_number', 'is_active')
    list_editable = ('is_active',)

