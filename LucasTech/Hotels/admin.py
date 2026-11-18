from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from core.admin_retour import RetourMixin

from .models import EQUIPEMENTS, Chambre, Hotel, PhotoChambre, PhotoHotel


class _AvecEquipements(forms.ModelForm):
    equipements = forms.MultipleChoiceField(label="Équipements", choices=EQUIPEMENTS, required=False,
                                            widget=forms.CheckboxSelectMultiple)


class HotelForm(_AvecEquipements):
    class Meta:
        model = Hotel
        fields = '__all__'


class ChambreForm(_AvecEquipements):
    class Meta:
        model = Chambre
        fields = '__all__'


class PhotoHotelInline(admin.TabularInline):
    model = PhotoHotel
    extra = 1
    fields = ['image', 'legende', 'ordre']


class ChambreInline(admin.TabularInline):
    model = Chambre
    form = ChambreForm
    extra = 0
    fields = ['nom', 'prix_nuit', 'capacite', 'actif', 'ordre']
    show_change_link = True  # photos et équipements : sur la fiche de la chambre


@admin.register(Hotel)
class HotelAdmin(RetourMixin, admin.ModelAdmin):
    form = HotelForm
    list_display = ['apercu', 'fiche', 'ville', 'quartier', 'etoiles', 'nb_chambres', 'vues', 'clics_reserver',
                    'clics_appel', 'actif', 'ordre']
    list_display_links = None  # un clic ouvre la fiche de l'hôtel (détails + chambres)
    list_editable = ['actif', 'ordre']
    list_filter = ['actif', 'ville', 'etoiles']
    search_fields = ['nom', 'ville', 'quartier', 'adresse', 'alias']
    readonly_fields = ['vues', 'clics_reserver', 'clics_appel']
    inlines = [PhotoHotelInline]  # les chambres se gèrent depuis la fiche de l'hôtel
    fieldsets = (
        (None, {'fields': ('nom', 'photo', 'legende_photo', 'description', 'etoiles', 'prix_min', 'equipements')}),
        ("Lieu", {'fields': ('ville', 'quartier', 'adresse', ('latitude', 'longitude'))}),
        ("Contacts du propriétaire", {'fields': ('telephone', 'whatsapp', 'site_web'),
                                      'description': "Sans WhatsApp, « Réserver » utilise notre numéro principal."}),
        ("Publication", {'fields': ('actif', 'ordre', 'alias')}),
    )

    def retour_defaut(self, h):
        return reverse('admin_hotel', args=[h.pk])

    def _lien(self, h, contenu):
        return format_html('<a href="{}">{}</a>', reverse('admin_hotel', args=[h.pk]), contenu)

    @admin.display(description="Hôtel", ordering='nom')
    def fiche(self, h):
        return self._lien(h, format_html('<b>{}</b>', h.nom))

    @admin.display(description="")
    def apercu(self, h):
        return self._lien(h, format_html('<img src="{}" style="width:56px;height:40px;object-fit:cover;border-radius:6px">',
                                         h.photo.url)) if h.photo else self._lien(h, '—')

    @admin.display(description="Chambres")
    def nb_chambres(self, h):
        return h.chambres.count()


class PhotoChambreInline(admin.TabularInline):
    model = PhotoChambre
    extra = 2
    fields = ['image', 'ordre']


@admin.register(Chambre)
class ChambreAdmin(RetourMixin, admin.ModelAdmin):
    form = ChambreForm
    list_display = ['nom', 'hotel', 'prix_nuit', 'capacite', 'vues', 'actif', 'ordre']
    list_filter = ['hotel', 'actif']
    list_editable = ['actif', 'ordre']
    search_fields = ['nom', 'hotel__nom']
    readonly_fields = ['vues']
    inlines = [PhotoChambreInline]

    def retour_defaut(self, c):
        return reverse('admin_hotel', args=[c.hotel_id])
