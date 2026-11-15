from django.contrib import admin
from django.utils.html import format_html

from .models import Repetiteur


@admin.register(Repetiteur)
class RepetiteurAdmin(admin.ModelAdmin):
    list_display = ['apercu', 'nom', 'matieres', 'ville', 'quartier', 'actif', 'ordre']
    list_display_links = ['apercu', 'nom']
    list_editable = ['actif', 'ordre']
    list_filter = ['actif', 'ville']
    search_fields = ['nom', 'matieres', 'ville', 'quartier', 'niveaux']
    fieldsets = (
        (None, {'fields': ('photo', 'nom', 'matieres', 'niveaux', 'experience', 'tarif', 'description')}),
        ('Lieu', {'fields': ('ville', 'quartier', 'latitude', 'longitude')}),
        ('Contact', {'fields': ('whatsapp', 'email', 'telephone')}),
        ('Publication', {'fields': ('actif', 'ordre')}),
    )

    @admin.display(description="")
    def apercu(self, r):
        if not r.photo:
            return '—'
        return format_html('<img src="{}" style="width:42px;height:42px;object-fit:cover;border-radius:10px">', r.photo.url)
