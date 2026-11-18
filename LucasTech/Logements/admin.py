from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import EQUIPEMENTS, Logement, PhotoLogement


class _PlusieursFichiers(forms.ClearableFileInput):
    allow_multiple_selected = True


class _ChampPhotos(forms.FileField):
    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            return [super(_ChampPhotos, self).clean(d, initial) for d in data if d]
        return [super().clean(data, initial)] if data else []


class LogementForm(forms.ModelForm):
    equipements = forms.MultipleChoiceField(label="Équipements", choices=EQUIPEMENTS, required=False,
                                            widget=forms.CheckboxSelectMultiple)
    photos_ajout = _ChampPhotos(label="Ajouter des photos", required=False,
                                widget=_PlusieursFichiers(attrs={'multiple': True, 'accept': 'image/*'}),
                                help_text="Sélectionnez plusieurs photos d'un coup.")

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
        (None, {'fields': ('type', ('ville', 'quartier'), ('loyer', 'periode'), 'pieces', 'meuble', 'photos_ajout',
                           'description')}),
        ("Propriétaire (privé, jamais affiché)", {'fields': ('proprietaire_nom', 'proprietaire_telephone')}),
        ("Plus de détails (facultatif)", {'classes': ('collapse',), 'fields': (
            'titre', 'repere', 'caution', ('compteur_eau', 'compteur_electricite'), 'equipements', 'disponible_le',
            ('latitude', 'longitude'), 'alias')}),
        ("Publication", {'fields': ('loue', 'ordre')}),
        ("Statistiques", {'classes': ('collapse',), 'fields': ('vues', 'contacts')}),
    )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        debut = form.instance.photos.count()
        for i, f in enumerate(form.cleaned_data.get('photos_ajout') or []):
            PhotoLogement.objects.create(logement=form.instance, image=f, ordre=debut + i)

    @admin.display(description="")
    def apercu(self, l):
        p = l.photos.first()
        return format_html('<img src="{}" style="width:56px;height:40px;object-fit:cover;border-radius:6px">',
                           p.image.url) if p else '—'

    @admin.display(description="Loyer", ordering='loyer')
    def loyer_aff(self, l):
        return f"{l.loyer:,} CFA {l.get_periode_display()}".replace(',', ' ')
