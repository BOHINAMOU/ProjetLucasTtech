from django.contrib import admin
from django.utils.html import format_html

from .models import Repetiteur


@admin.register(Repetiteur)
class RepetiteurAdmin(admin.ModelAdmin):
    class Media:
        css = {'all': ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',)}
        js = ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', 'admin/carte_produit.js')

    list_display = ['apercu', 'nom', 'matieres', 'ville', 'quartier', 'actif', 'ordre']
    list_display_links = ['apercu', 'nom']
    list_editable = ['actif', 'ordre']
    list_filter = ['actif', 'ville']
    search_fields = ['nom', 'matieres', 'ville', 'quartier', 'niveaux']
    fieldsets = (
        (None, {'fields': ('photo', 'photo_apercu', 'nom', 'matieres', 'niveaux', 'experience', 'tarif', 'description')}),
        ('Lieu', {'fields': ('ville', 'quartier', 'latitude', 'longitude'),
                  'description': "Facultatif : choisissez le lieu sur la carte (recherche, clic ou « Ma position »)."}),
        ('Contact', {'fields': ('whatsapp', 'email', 'telephone')}),
        ('Publication', {'fields': ('actif', 'ordre')}),
    )

    readonly_fields = ['photo_apercu']

    @admin.display(description="Aperçu")
    def photo_apercu(self, r):
        if not r.photo:
            return '—'
        return format_html('<img src="{}" style="width:120px;height:120px;object-fit:cover;border-radius:16px">', r.photo.url)

    @admin.display(description="")
    def apercu(self, r):
        if not r.photo:
            return '—'
        return format_html('<img src="{}" style="width:42px;height:42px;object-fit:cover;border-radius:10px">', r.photo.url)
