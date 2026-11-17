from django.contrib import admin, messages
from django.db.models import Count, Q, Sum

from .models import ReglageLivraison, Reversement, Vendeur


def francs(n):
    return f"{int(n or 0):,} CFA".replace(',', '\u202f')


def comptes(v):
    """Chiffres d'un vendeur : ventes payées, commission, dû, reversé, reste à reverser."""
    from Payments.models import Payment
    qs = Payment.objects.filter(vendeur=v, status='approved')
    a = qs.aggregate(n=Count('pk'), total=Sum('amount'), remise=Sum('remise'), com=Sum('commission'))
    du = (a['total'] or 0) + (a['remise'] or 0) - (a['com'] or 0)  # la remise d'un code promo est payée par Lantante
    reverse = v.reversements.aggregate(s=Sum('montant'))['s'] or 0
    return {'ventes': a['n'], 'encaisse': a['total'] or 0, 'commission': a['com'] or 0, 'du': du,
            'reverse': reverse, 'reste': du - reverse}


class ReversementInline(admin.TabularInline):
    model = Reversement
    extra = 0
    fields = ['date', 'montant', 'reference', 'note']

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Vendeur)
class VendeurAdmin(admin.ModelAdmin):
    list_display = ['boutique', 'user', 'ville', 'statut', 'commission_pct', 'ventes', 'du_f', 'reste_f']
    list_filter = ['statut', 'ville']
    search_fields = ['boutique', 'user__email', 'ville']
    autocomplete_fields = ['user']
    inlines = [ReversementInline]
    readonly_fields = ['chiffres']
    fieldsets = (
        (None, {'fields': ('user', 'boutique', 'whatsapp', 'statut')}),
        ('Point de retrait', {'fields': ('ville', 'adresse_retrait', 'latitude', 'longitude'),
                              'description': "Position GPS : dans Google Maps, appui long sur le lieu, puis copier les deux nombres."}),
        ('Argent', {'fields': ('commission_pct', 'numero_reversement', 'chiffres')}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(user=request.user)

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return self.readonly_fields
        return ['user', 'boutique', 'whatsapp', 'statut', 'ville', 'adresse_retrait', 'latitude', 'longitude',
                'commission_pct', 'numero_reversement', 'chiffres']

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Ventes")
    def ventes(self, v):
        return comptes(v)['ventes']

    @admin.display(description="Dû au vendeur")
    def du_f(self, v):
        return francs(comptes(v)['du'])

    @admin.display(description="Reste à reverser")
    def reste_f(self, v):
        return francs(comptes(v)['reste'])

    @admin.display(description="Chiffres")
    def chiffres(self, v):
        if not v.pk:
            return "-"
        c = comptes(v)
        return (f"{c['ventes']} ventes · encaissé {francs(c['encaisse'])} · commission {francs(c['commission'])} · "
                f"dû {francs(c['du'])} · reversé {francs(c['reverse'])} · reste {francs(c['reste'])}")

    def save_formset(self, request, form, formset, change):
        for obj in formset.save(commit=False):
            if obj.par_id is None:
                obj.par = request.user
            obj.save()

    def changelist_view(self, request, extra_context=None):
        if request.user.is_superuser:
            reste = sum(comptes(v)['reste'] for v in Vendeur.objects.all())
            self.message_user(request, f"Reste à reverser à tous les vendeurs : {francs(reste)}.", messages.INFO)
        return super().changelist_view(request, extra_context)


@admin.register(ReglageLivraison)
class ReglageLivraisonAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'rayon_ville_km', 'distance_defaut_km']

    def has_add_permission(self, request):
        return not ReglageLivraison.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Reversement)
class ReversementAdmin(admin.ModelAdmin):
    list_display = ['date', 'vendeur', 'montant', 'reference', 'par']
    list_filter = ['vendeur']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(vendeur__user=request.user)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if obj.par_id is None:
            obj.par = request.user
        super().save_model(request, obj, form, change)


# ── Demandes « Vendre sur Lantante » et catégories privées des vendeurs ──
from django import forms as _forms
from django.urls import reverse as _reverse
from django.utils.html import format_html as _fh

from . import demandes as _dem
from .models import CategorieVendeur, DemandeVendeur


class _DecisionVendeur(_forms.ModelForm):
    decision = _forms.ChoiceField(label="Décision", required=False, choices=[
        ('', '— Pas de décision —'), ('accepter', 'Accepter et créer son espace'),
        ('corriger', 'Demander une correction'), ('refuser', 'Refuser')])

    class Meta:
        model = DemandeVendeur
        fields = '__all__'

    def clean(self):
        d = super().clean()
        if d.get('decision') in ('corriger', 'refuser') and not (d.get('motif') or '').strip():
            self.add_error('motif', "Le motif est obligatoire pour une correction ou un refus.")
        return d


@admin.register(DemandeVendeur)
class DemandeVendeurAdmin(admin.ModelAdmin):
    form = _DecisionVendeur
    list_display = ['boutique', 'ville', 'activite', 'statut', 'created_at']
    list_filter = ['statut', 'ville']
    search_fields = ['boutique', 'nom', 'prenom', 'telephone', 'email']
    readonly_fields = ['statut', 'vendeur', 'piece_lien', 'decide_le', 'created_at', 'updated_at']
    fieldsets = (
        ("Décision", {'fields': ('statut', 'decision', 'motif', 'vendeur')}),
        ("Boutique", {'fields': ('boutique', 'activite', 'ville')}),
        ("Responsable", {'fields': ('prenom', 'nom', 'telephone', 'whatsapp', 'email')}),
        ("Pièce d'identité (privée)", {'fields': ('piece_type', 'piece_numero', 'piece_lien')}),
        ("Suivi", {'fields': ('decide_le', 'created_at', 'updated_at')}),
    )

    @admin.display(description="Pièce")
    def piece_lien(self, d):
        if not d.piece:
            return '—'
        return _fh('<a class="button" target="_blank" rel="noopener" href="{}">Voir la pièce</a>',
                   _reverse('vendre:piece', args=[d.pk]))

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        dec = form.cleaned_data.get('decision')
        if dec == 'accepter':
            _dem.accepter(obj)
        elif dec == 'corriger':
            _dem.demander_correction(obj, obj.motif)
        elif dec == 'refuser':
            _dem.refuser(obj, obj.motif)


@admin.register(CategorieVendeur)
class CategorieVendeurAdmin(admin.ModelAdmin):
    """Un vendeur range ses produits dans ses propres catégories ; l'équipe ne s'en sert pas."""
    list_display = ['nom', 'nb_produits']
    search_fields = ['nom']

    def get_queryset(self, request):
        from .acces import vendeur_de
        qs = super().get_queryset(request)
        v = vendeur_de(request.user)
        return qs.filter(vendeur=v) if v else qs

    def get_fields(self, request, obj=None):
        from .acces import vendeur_de
        return ['nom'] if vendeur_de(request.user) else ['vendeur', 'nom']

    @admin.display(description="Produits")
    def nb_produits(self, c):
        return c.produits.count()

    def save_model(self, request, obj, form, change):
        from .acces import vendeur_de
        v = vendeur_de(request.user)
        if v:
            obj.vendeur = v
        super().save_model(request, obj, form, change)
