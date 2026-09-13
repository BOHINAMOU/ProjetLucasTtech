# Fichier : Shop/admin.py
from django.contrib import admin
from .models import Category, Product, ProductImage, ShopOrder, ShopOrderItem, Reservation, Review


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
    list_display = (
        'receipt_number', 
        'user', 
        'total_price', 
        'status', 
        'payment_method', 
        'created_at'
    )
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
    search_fields = ('name', 'description')
    inlines = [ProductImageInline]

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'product', 'status', 'created_at')
    list_filter = ('status',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating',)

