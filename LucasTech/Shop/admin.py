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
    list_display = ('name', 'order', 'slug')
    list_editable = ('order',)
    prepopulated_fields = {'slug': ('name',)}

from django import forms  # noqa: E402


class ProduitForm(forms.ModelForm):
    """WhatsApp obligatoire : le bouton du produit contacte celui qui l'a ajouté."""
    class Meta:
        model = Product
        fields = '__all__'

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        f = self.fields.get('contact_whatsapp')
        if f:
            f.required = True
            f.label = "WhatsApp de contact"
            f.help_text = "Numéro de celui qui vend ce produit. Format : 22890000000."

    def clean_contact_whatsapp(self):
        v = ''.join(c for c in (self.cleaned_data.get('contact_whatsapp') or '') if c.isdigit())
        if len(v) < 8:
            raise forms.ValidationError("Numéro WhatsApp invalide.")
        return v


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
        ('Stock et affichage', {'fields': ('stock', 'is_available', 'is_featured')}),
        ('Contact et livraison', {'fields': ('mode_commande', 'contact_whatsapp', 'livrable', 'retrait_latitude', 'retrait_longitude',
                                             'livraison_autre_ville', 'vendeur')}),
    )

    class Media:
        css = {'all': ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',)}
        js = ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', 'admin/carte_produit.js')

    def get_form(self, request, obj=None, **kwargs):
        from Marche.acces import vendeur_de
        kwargs['form'] = ProduitForm
        form = super().get_form(request, obj, **kwargs)
        v = vendeur_de(request.user)
        if obj is None and 'contact_whatsapp' in form.base_fields:
            form.base_fields['contact_whatsapp'].initial = v.whatsapp if v else ''
        return form

    # Un vendeur ne voit et ne modifie que SES produits ; le vendeur est mis d'office.
    def get_queryset(self, request):
        from Marche.acces import vendeur_de
        qs = super().get_queryset(request)
        v = vendeur_de(request.user)
        return qs.filter(vendeur=v) if v else qs

    def get_fieldsets(self, request, obj=None):
        from Marche.acces import vendeur_de
        if not vendeur_de(request.user):
            return self.fieldsets
        return (
            (None, {'fields': ('categorie_vendeur', 'name', 'short_description', 'description')}),
            ('Prix', {'fields': ('price', 'old_price')}),
            ('Photos', {'fields': ('image',)}),
            ('Stock', {'fields': ('stock', 'is_available')}),
            ('Contact et livraison', {'fields': ('mode_commande', 'contact_whatsapp', 'livrable', 'retrait_latitude', 'retrait_longitude',
                                                 'livraison_autre_ville')}),
        )

    def get_list_filter(self, request):
        from Marche.acces import vendeur_de
        return ('is_available',) if vendeur_de(request.user) else ('category', 'vendeur', 'is_available', 'is_featured')

    def save_model(self, request, obj, form, change):
        from Marche.acces import vendeur_de
        v = vendeur_de(request.user)
        if v:
            obj.vendeur = v
            if not obj.category_id:  # rangé pour l'appli dans « Boutiques partenaires » (catégories privées à part)
                from .models import Category
                obj.category, _ = Category.objects.get_or_create(
                    slug='boutiques-partenaires', defaults={'name': 'Boutiques partenaires'})
            if obj.categorie_vendeur_id and obj.categorie_vendeur.vendeur_id != v.pk:
                obj.categorie_vendeur = None
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'categorie_vendeur':
            from Marche.acces import vendeur_de
            from Marche.models import CategorieVendeur
            v = vendeur_de(request.user)
            kwargs['queryset'] = CategorieVendeur.objects.filter(vendeur=v) if v else CategorieVendeur.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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

