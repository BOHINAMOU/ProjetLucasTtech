from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Repetiteur


@admin.register(Repetiteur)
class RepetiteurAdmin(admin.ModelAdmin):
    class Media:
        css = {'all': ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',)}
        js = ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', 'admin/carte_produit.js')

    list_display = ['apercu', 'nom', 'matieres', 'ville', 'quartier', 'est_exemple', 'actif', 'ordre']
    list_display_links = ['apercu', 'nom']
    list_editable = ['actif', 'ordre']
    list_filter = ['actif', 'est_exemple', 'ville']
    actions = ['supprimer_exemples']
    search_fields = ['nom', 'matieres', 'ville', 'quartier', 'niveaux']
    fieldsets = (
        (None, {'fields': ('photo', 'photo_apercu', 'nom', 'matieres', 'niveaux', 'experience', 'tarif', 'description')}),
        ('Lieu', {'fields': ('ville', 'quartier', 'latitude', 'longitude'),
                  'description': "Facultatif : choisissez le lieu sur la carte (recherche, clic ou « Ma position »)."}),
        ('Contact', {'fields': ('whatsapp', 'email', 'telephone')}),
        ('Publication', {'fields': ('actif', 'est_exemple', 'ordre')}),
    )

    readonly_fields = ['photo_apercu']

    def changelist_view(self, request, extra_context=None):
        # « Supprimer tous les exemples » marche sans rien cocher.
        if request.method == 'POST' and request.POST.get('action') == 'supprimer_exemples'                 and not request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME):
            post = request.POST.copy()
            post.setlist(admin.helpers.ACTION_CHECKBOX_NAME, [str(p) for p in Repetiteur.objects.values_list('pk', flat=True)[:1]])
            request.POST = post
        return super().changelist_view(request, extra_context)

    @admin.action(description="Supprimer tous les exemples")
    def supprimer_exemples(self, request, queryset):
        n, _ = Repetiteur.objects.filter(est_exemple=True).delete()
        self.message_user(request, f"{n} exemple(s) supprimé(s).", messages.SUCCESS)

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


# ── Candidatures répétiteurs ──
from django import forms as _forms
from django.urls import reverse as _reverse

from . import candidatures as _cand
from .models import Candidature, HistoriqueCandidature, ReglageCandidature


@admin.register(ReglageCandidature)
class ReglageCandidatureAdmin(admin.ModelAdmin):
    list_display = ['__str__']

    def has_add_permission(self, request):
        return not ReglageCandidature.objects.exists()


class _HistoriqueInline(admin.TabularInline):
    model = HistoriqueCandidature
    extra = 0
    can_delete = False
    readonly_fields = ['date', 'auteur', 'action', 'motif']

    def has_add_permission(self, request, obj=None):
        return False


class _DecisionForm(_forms.ModelForm):
    DECISIONS = [('', '— Pas de décision —'), ('valider', 'Valider et publier'),
                 ('corriger', 'Demander une correction'), ('rejeter', 'Rejeter')]
    decision = _forms.ChoiceField(label="Décision", choices=DECISIONS, required=False)

    class Meta:
        model = Candidature
        fields = '__all__'

    def clean(self):
        d = super().clean()
        if d.get('decision') in ('corriger', 'rejeter') and not (d.get('motif') or '').strip():
            self.add_error('motif', "Le motif est obligatoire pour une correction ou un rejet.")
        if d.get('decision') == 'valider' and self.instance.statut not in ('a_verifier', 'a_corriger'):
            self.add_error('decision', "Seul un dossier payé peut être validé.")
        return d


@admin.register(Candidature)
class CandidatureAdmin(admin.ModelAdmin):
    form = _DecisionForm
    list_display = ['nom_complet', 'matieres', 'ville', 'statut', 'paiement', 'updated_at']
    list_filter = ['statut', 'ville', 'piece_type']
    search_fields = ['nom', 'prenom', 'telephone', 'email', 'matieres']
    inlines = [_HistoriqueInline]
    readonly_fields = ['user', 'statut', 'paiement', 'repetiteur', 'apercu_photo', 'piece', 'decide_le',
                       'pieces_supprimees', 'created_at', 'updated_at']
    fieldsets = (
        ("Décision", {'fields': ('statut', 'decision', 'motif', 'paiement', 'repetiteur')}),
        ("Identité", {'fields': ('user', 'prenom', 'nom', 'telephone', 'whatsapp', 'email')}),
        ("Profil", {'fields': ('apercu_photo', 'photo', 'matieres', 'niveaux', 'experience', 'tarif', 'description',
                               'ville', 'quartier', 'latitude', 'longitude')}),
        ("Pièce d'identité (privée)", {'fields': ('piece_type', 'piece_numero', 'piece', 'pieces_supprimees')}),
        ("Suivi", {'fields': ('decide_le', 'created_at', 'updated_at')}),
    )

    @admin.display(description="Photo")
    def apercu_photo(self, c):
        return format_html('<img src="{}" style="width:110px;height:110px;object-fit:cover;border-radius:14px">',
                           c.photo.url) if c.photo else '—'

    @admin.display(description="Pièce")
    def piece(self, c):
        if c.pieces_supprimees:
            return "Supprimée (90 jours après la décision)"
        liens = [format_html('<a href="{}" target="_blank" rel="noopener" class="button">Voir le {}</a>',
                             _reverse('repetiteurs:piece', args=[c.pk, cote]), cote)
                 for cote, f in (('recto', c.piece_recto), ('verso', c.piece_verso)) if f]
        return format_html(' '.join(['{}'] * len(liens)), *liens) if liens else '—'

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        d = form.cleaned_data.get('decision')
        if d == 'valider':
            _cand.valider(obj, request.user)
        elif d == 'corriger':
            _cand.demander_correction(obj, obj.motif, request.user)
        elif d == 'rejeter':
            _cand.rejeter(obj, obj.motif, request.user)
