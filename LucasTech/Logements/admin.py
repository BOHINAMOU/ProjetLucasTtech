from django import forms
from django.contrib import admin
from django.utils.html import format_html

from urllib.parse import quote

from django.contrib import messages

from .models import EQUIPEMENTS, DemandeLogement, Logement, PhotoLogement


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
    list_display = ['apercu', 'nom', 'statut_pilule', 'type', 'ville', 'quartier', 'loyer_aff', 'meuble', 'vues', 'contacts', 'loue', 'ordre']
    list_display_links = ['apercu', 'nom']
    list_editable = ['loue', 'ordre']
    list_filter = ['statut', 'loue', 'ville', 'type', 'meuble', 'periode']
    actions = ['valider', 'refuser']
    search_fields = ['titre', 'quartier', 'ville', 'repere', 'alias', 'proprietaire_nom', 'proprietaire_telephone']
    readonly_fields = ['vues', 'contacts', 'whatsapp_proposeur']
    inlines = [PhotoInline]
    fieldsets = (
        (None, {'fields': ('type', ('ville', 'quartier'), ('loyer', 'periode'), 'pieces', 'meuble', 'photos_ajout',
                           'description')}),
        ("Propriétaire (privé, jamais affiché)", {'fields': ('proprietaire_nom', 'proprietaire_telephone', 'propose_par_role', 'whatsapp_proposeur')}),
        ("Plus de détails (facultatif)", {'classes': ('collapse',), 'fields': (
            'titre', 'repere', 'caution', ('compteur_eau', 'compteur_electricite'), 'equipements', 'disponible_le',
            ('latitude', 'longitude'), 'alias')}),
        ("Publication", {'fields': ('statut', 'loue', 'ordre')}),
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

    @admin.display(description="Statut", ordering='statut')
    def statut_pilule(self, l):
        c = {'publie': ('#E3F5EC', '#0B5A38'), 'attente': ('#FBF4DF', '#8A6A0E'), 'refuse': ('#FBE9E7', '#C0392B')}[l.statut]
        return format_html('<span style="background:{};color:{};border-radius:999px;padding:3px 10px;font-weight:700;font-size:.8rem">{}</span>',
                           c[0], c[1], l.get_statut_display())

    @admin.display(description="WhatsApp")
    def whatsapp_proposeur(self, l):
        if not l.proprietaire_telephone:
            return '—'
        t = ''.join(c for c in l.proprietaire_telephone if c.isdigit())
        return format_html('<a class="btn btn-success btn-sm" href="https://wa.me/{}?text={}" target="_blank" rel="noopener">Écrire sur WhatsApp</a>',
                           t, quote(f"Bonjour, c'est Lantante. Au sujet de votre logement : {l.nom}."))

    @admin.action(description="Valider (mettre en ligne)")
    def valider(self, request, qs):
        n = qs.exclude(statut='publie').update(statut='publie')
        messages.success(request, f"{n} logement(s) en ligne.")

    @admin.action(description="Refuser (ne pas publier)")
    def refuser(self, request, qs):
        n = qs.update(statut='refuse')
        messages.success(request, f"{n} logement(s) refusé(s).")


@admin.register(DemandeLogement)
class DemandeLogementAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type', 'lieu', 'budget_aff', 'date_souhaitee', 'statut', 'created_at']
    list_filter = ['statut', 'type']
    list_editable = ['statut']
    search_fields = ['nom', 'telephone', 'lieu', 'message']
    readonly_fields = ['repondre', 'created_at']
    fields = ['repondre', 'nom', 'telephone', 'type', 'lieu', 'budget', 'date_souhaitee', 'message', 'statut', 'note', 'created_at']
    actions = ['marquer_traitee']

    @admin.display(description="Budget", ordering='budget')
    def budget_aff(self, d):
        return f"{d.budget:,} CFA".replace(',', ' ')

    @admin.display(description="Répondre")
    def repondre(self, d):
        if not d.pk:
            return '—'
        texte = f"Bonjour {d.nom}, c'est Lantante. Au sujet de votre recherche : {d.get_type_display()} à {d.lieu}."
        return format_html('<a class="btn btn-success" href="https://wa.me/{}?text={}" target="_blank" rel="noopener">'
                           '<i class="fab fa-whatsapp"></i> Répondre sur WhatsApp</a>', d.telephone, quote(texte))

    @admin.action(description="Marquer comme traitée")
    def marquer_traitee(self, request, qs):
        qs.update(statut='traitee')
