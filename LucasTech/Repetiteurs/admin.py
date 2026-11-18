from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Repetiteur


@admin.register(Repetiteur)
class RepetiteurAdmin(admin.ModelAdmin):
    class Media:
        css = {'all': ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',)}
        js = ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', 'admin/carte_produit.js')

    list_display = ['apercu', 'nom', 'matieres', 'ville', 'affichage', 'est_service_lantante', 'est_exemple', 'actif', 'ordre']
    list_display_links = ['apercu', 'nom']
    list_editable = ['actif', 'ordre']
    list_filter = ['actif', 'est_service_lantante', 'est_exemple', 'ville', 'fin_affichage']
    actions = ['reactiver_1', 'reactiver_3', 'reactiver_6', 'reactiver_12', 'supprimer_exemples']
    search_fields = ['nom', 'matieres', 'ville', 'quartier', 'niveaux']
    fieldsets = (
        (None, {'fields': ('photo', 'photo_apercu', 'nom', 'matieres', 'niveaux', 'experience', 'tarif', 'description')}),
        ('Lieu', {'fields': ('ville', 'quartier', 'latitude', 'longitude'),
                  'description': "Facultatif : choisissez le lieu sur la carte (recherche, clic ou « Ma position »)."}),
        ('Contact', {'fields': ('whatsapp', 'email', 'telephone')}),
        ('Publication', {'fields': ('actif', 'fin_affichage', 'est_service_lantante', 'est_exemple', 'ordre')}),
    )

    readonly_fields = ['photo_apercu']

    @admin.display(description="Affichage")
    def affichage(self, r):
        if not r.fin_affichage:
            return "Sans limite"
        return format_html('<span style="color:{}">{} {:%d/%m/%Y}</span>', '#c62828' if r.expire else '#0b6137',
                           "Expiré le" if r.expire else "Jusqu'au", r.fin_affichage)

    def _reactiver(self, request, queryset, mois):
        from django.utils import timezone
        from .models import ajouter_mois
        fin = ajouter_mois(timezone.localdate(), mois)
        n = queryset.update(actif=True, fin_affichage=fin, rappel_fin_envoye=None)
        self.message_user(request, f"{n} profil(s) visible(s) jusqu'au {fin:%d/%m/%Y}.", messages.SUCCESS)

    @admin.action(description="Réactiver pour 1 mois")
    def reactiver_1(self, request, queryset):
        self._reactiver(request, queryset, 1)

    @admin.action(description="Réactiver pour 3 mois")
    def reactiver_3(self, request, queryset):
        self._reactiver(request, queryset, 3)

    @admin.action(description="Réactiver pour 6 mois")
    def reactiver_6(self, request, queryset):
        self._reactiver(request, queryset, 6)

    @admin.action(description="Réactiver pour 12 mois")
    def reactiver_12(self, request, queryset):
        self._reactiver(request, queryset, 12)

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
    duree = _forms.TypedChoiceField(label="Durée d'affichage (si validée)", coerce=int, initial=3, required=False,
                                    choices=[(1, '1 mois'), (3, '3 mois'), (6, '6 mois'), (12, '12 mois')])
    fin_le = _forms.DateField(label="Ou jusqu'au", required=False, widget=_forms.DateInput(attrs={'type': 'date'}),
                              help_text="Facultatif : remplace la durée.")

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
        ("Décision", {'fields': ('statut', 'decision', 'duree', 'fin_le', 'motif', 'paiement', 'repetiteur')}),
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
            _cand.valider(obj, request.user, mois=form.cleaned_data.get('duree') or 3,
                          fin=form.cleaned_data.get('fin_le'))
        elif d == 'corriger':
            _cand.demander_correction(obj, obj.motif, request.user)
        elif d == 'rejeter':
            _cand.rejeter(obj, obj.motif, request.user)
