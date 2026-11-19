from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import CategoriePlat, GroupeOptions, PhotoPlat, PhotoRestaurant, Plat, Restaurant, lire_options


def _img(f, w=56, h=42):
    return format_html('<img src="{}" style="width:{}px;height:{}px;object-fit:cover;border-radius:8px">', f.url, w, h) if f else '—'


class GroupeForm(forms.ModelForm):
    class Meta:
        model = GroupeOptions
        fields = '__all__'
        widgets = {'options_texte': forms.Textarea(attrs={'rows': 4, 'placeholder': "Alloco | 500\nFrites | 700\nSans piment | 0"})}

    def clean_options_texte(self):
        t = self.cleaned_data.get('options_texte') or ''
        if not lire_options(t):
            raise forms.ValidationError("Ajoutez au moins une option (une par ligne).")
        return t


class PhotoRestaurantInline(admin.TabularInline):
    model = PhotoRestaurant
    extra = 2
    fields = ['image', 'legende', 'ordre']


class CategorieInline(admin.TabularInline):
    model = CategoriePlat
    extra = 1
    fields = ['nom', 'ordre']


class PlatInline(admin.TabularInline):
    """Ajout rapide : nom, prix, photo. Les options se règlent sur la fiche du plat."""
    model = Plat
    extra = 3
    fields = ['apercu', 'nom', 'prix', 'image', 'categorie', 'disponible', 'ordre']
    readonly_fields = ['apercu']
    show_change_link = True

    @admin.display(description="")
    def apercu(self, p):
        return _img(p.image) if p and p.pk else ''

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'categorie':
            rid = request.resolver_match.kwargs.get('object_id') if request.resolver_match else None
            kwargs['queryset'] = CategoriePlat.objects.filter(restaurant_id=rid) if rid else CategoriePlat.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class GroupeRestaurantInline(admin.StackedInline):
    model = GroupeOptions
    form = GroupeForm
    fk_name = 'restaurant'
    extra = 0
    fields = [('nom', 'choix'), ('obligatoire', 'avec_quantite'), 'options_texte', 'ordre']
    verbose_name = "Options pour tous les plats"
    verbose_name_plural = "Options pour tous les plats (ex. Boissons)"

    def get_queryset(self, request):
        return super().get_queryset(request).filter(plat__isnull=True)


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ['logo_aff', 'nom', 'lieu', 'nb_plats', 'visible', 'vues', 'clics_commander']
    list_display_links = ['logo_aff', 'nom']
    list_editable = ['visible']
    list_filter = ['visible', 'ville']
    search_fields = ['nom', 'quartier', 'ville', 'adresse']
    readonly_fields = ['vues', 'clics_commander']
    inlines = [PhotoRestaurantInline, CategorieInline, PlatInline, GroupeRestaurantInline]
    fieldsets = (
        (None, {'fields': ('nom', ('logo', 'couverture'), 'description', 'visible')}),
        ("Lieu", {'fields': (('quartier', 'ville'), 'adresse', ('latitude', 'longitude'))}),
        ("Contact et horaires", {'fields': (('telephone', 'whatsapp'), 'horaires', 'livraison')}),
        ("Statistiques", {'classes': ('collapse',), 'fields': (('vues', 'clics_commander'), 'ordre')}),
    )

    @admin.display(description="")
    def logo_aff(self, r):
        return _img(r.logo or r.couverture, 44, 44)

    @admin.display(description="Plats")
    def nb_plats(self, r):
        return r.plats.count()


class PhotoPlatInline(admin.TabularInline):
    model = PhotoPlat
    extra = 1
    fields = ['image', 'ordre']


class GroupePlatInline(admin.StackedInline):
    model = GroupeOptions
    form = GroupeForm
    fk_name = 'plat'
    extra = 1
    fields = [('nom', 'choix'), ('obligatoire', 'avec_quantite'), 'options_texte', 'ordre']
    verbose_name = "Groupe d'options (ex. Accompagnements)"
    verbose_name_plural = "Options du plat (accompagnements, boissons, fruits…)"


@admin.register(Plat)
class PlatAdmin(admin.ModelAdmin):
    list_display = ['image_aff', 'nom', 'restaurant', 'prix', 'disponible', 'ordre']
    list_display_links = ['image_aff', 'nom']
    list_editable = ['disponible', 'ordre']
    list_filter = ['restaurant', 'disponible']
    search_fields = ['nom', 'restaurant__nom']
    fields = ['restaurant', 'categorie', 'nom', 'prix', 'image', 'description', 'disponible', 'ordre']
    inlines = [PhotoPlatInline, GroupePlatInline]

    @admin.display(description="")
    def image_aff(self, p):
        return _img(p.image)

    def save_formset(self, request, form, formset, change):
        objs = formset.save(commit=False)
        for o in objs:
            if isinstance(o, GroupeOptions):
                o.restaurant_id = form.instance.restaurant_id
            o.save()
        for o in formset.deleted_objects:
            o.delete()
        formset.save_m2m()
