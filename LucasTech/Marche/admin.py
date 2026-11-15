from django.contrib import admin, messages
from django.db.models import Count, Q, Sum

from .models import ReglageLivraison, Reversement, Vendeur


def francs(n):
    return f"{int(n or 0):,} F".replace(',', '\u202f')


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
