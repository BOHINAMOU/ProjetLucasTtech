from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import EQUIPEMENTS, Logement, PhotoLogement


class LogementForm(forms.ModelForm):
    equipements = forms.MultipleChoiceField(label="Équipements", choices=EQUIPEMENTS, required=False,
                                            widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Logement
        fields = '__all__'


class PhotoInline(admin.TabularInline):
    model = PhotoLogement
    extra = 3
    fields = ['image', 'ordre']


@admin.register(Logement)
class LogementAdmin(admin.ModelAdmin):
    form = LogementForm
    list_display = ['apercu', 'nom', 'type', 'ville', 'quartier', 'loyer_aff', 'meuble', 'vues', 'contacts', 'loue', 'ordre']
    list_display_links = ['apercu', 'nom']
    list_editable = ['loue', 'ordre']
    list_filter = ['loue', 'ville', 'type', 'meuble', 'periode']
    search_fields = ['titre', 'quartier', 'ville', 'repere', 'alias', 'proprietaire_nom', 'proprietaire_telephone']
    readonly_fields = ['vues', 'contacts']
    inlines = [PhotoInline]
    fieldsets = (
        (None, {'fields': ('type', 'titre', 'description')}),
        ("Lieu", {'fields': ('ville', 'quartier', 'repere', ('latitude', 'longitude'), 'alias')}),
        ("Prix", {'fields': (('loyer', 'periode'), 'caution')}),
        ("Caractéristiques", {'fields': ('pieces', 'meuble', ('compteur_eau', 'compteur_electricite'), 'equipements',
                                         'disponible_le')}),
        ("Propriétaire (privé, jamais affiché)", {'fields': ('proprietaire_nom', 'proprietaire_telephone')}),
        ("Publication", {'fields': ('loue', 'ordre')}),
        ("Statistiques", {'fields': ('vues', 'contacts')}),
    )

    @admin.display(description="")
    def apercu(self, l):
        p = l.photos.first()
        return format_html('<img src="{}" style="width:56px;height:40px;object-fit:cover;border-radius:6px">',
                           p.image.url) if p else '—'

    @admin.display(description="Loyer", ordering='loyer')
    def loyer_aff(self, l):
        return f"{l.loyer:,} CFA {l.get_periode_display()}".replace(',', ' ')
