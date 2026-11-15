import csv

from django.contrib import admin, messages
from django.contrib.admin.actions import delete_selected
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from . import services
from .models import Payment

PAYES = ('approved', 'refunded')  # lignes avec de l'argent : jamais supprimées, seulement marquées
COULEURS = {'approved': ('#0B7A4B', '#E3F5EC'), 'pending': ('#9A6700', '#FFF4D6'), 'declined': ('#B42318', '#FDECEA'),
            'canceled': ('#475569', '#EEF1F5'), 'refunded': ('#6D28D9', '#EEE7FD')}


def francs(n):
    return f"{int(n or 0):,} F".replace(',', '\u202f')


def badge_statut(p):
    fg, bg = COULEURS.get(p.status, ('#334155', '#EEF1F5'))
    return format_html('<span style="background:{};color:{};padding:3px 10px;border-radius:999px;font-weight:700;'
                       'font-size:12px;white-space:nowrap">{}</span>', bg, fg, p.get_status_display())


def export_csv(queryset, nom):
    r = HttpResponse(content_type='text/csv; charset=utf-8')
    r['Content-Disposition'] = f'attachment; filename="{nom}-{timezone.localdate():%Y-%m-%d}.csv"'
    r.write('\ufeff')  # accents corrects dans Excel
    w = csv.writer(r, delimiter=';')
    w.writerow(['Référence', 'Date', 'Prénom', 'Nom', 'Téléphone', 'WhatsApp', 'E-mail', 'Objet', 'Événement',
                'Détail', 'Montant (F)', 'Statut', 'Opérateur', 'Réf. FedaPay', 'Payé le'])
    for p in queryset.select_related('event'):
        detail = ', '.join(f"{i.get('name', '')} × {i.get('quantity', '')}" for i in (p.items or []) if isinstance(i, dict))
        w.writerow([p.reference, timezone.localtime(p.created_at).strftime('%d/%m/%Y %H:%M'), p.first_name, p.last_name,
                    p.phone, p.whatsapp, p.email, p.description, p.event.title if p.event_id else '', detail, p.amount,
                    p.get_status_display(), p.operator, p.fedapay_id,
                    timezone.localtime(p.paid_at).strftime('%d/%m/%Y %H:%M') if p.paid_at else ''])
    return r


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['reference', 'date', 'client', 'phone', 'description', 'montant', 'statut', 'operator']
    list_display_links = ['reference', 'client']
    list_filter = ['status', 'kind', ('event', admin.RelatedOnlyFieldListFilter), 'mode', 'created_at']
    search_fields = ['reference', 'description', 'first_name', 'last_name', 'email', 'phone', 'whatsapp', 'city',
                     'fedapay_id', 'event__title']
    readonly_fields = [f.name for f in Payment._meta.fields]
    date_hierarchy = 'created_at'
    list_per_page = 50
    actions = ['exporter_csv', 'supprimer_non_payes', 'marquer_rembourse', 'marquer_annule', 'verify_with_fedapay']
    change_list_template = 'admin/Payments/payment/change_list.html'

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        from core.delegations import paiements_visibles
        return paiements_visibles(request.user, super().get_queryset(request))

    def has_delete_permission(self, request, obj=None):
        # Un paiement réussi ou remboursé reste dans l'historique (trace de l'argent).
        if obj is not None and obj.status in PAYES:
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        a = super().get_actions(request)
        a.pop('delete_selected', None)  # remplacée par « Supprimer (non payés seulement) »
        return a

    @admin.display(description="Date", ordering='created_at')
    def date(self, p):
        return timezone.localtime(p.created_at).strftime('%d/%m/%Y %H:%M')

    @admin.display(description="Client", ordering='last_name')
    def client(self, p):
        return f"{p.first_name} {p.last_name}".strip() or '—'

    @admin.display(description="Montant", ordering='amount')
    def montant(self, p):
        return francs(p.amount)

    @admin.display(description="Statut", ordering='status')
    def statut(self, p):
        return badge_statut(p)

    def changelist_view(self, request, extra_context=None):
        r = super().changelist_view(request, extra_context=extra_context)
        try:
            qs = r.context_data['cl'].queryset
            ok = qs.filter(status='approved')
            r.context_data['resume'] = {
                'encaisse': francs(ok.aggregate(s=Sum('amount'))['s']),
                'payeurs': ok.count(),
                'attente': qs.filter(status='pending').count(),
                'echecs': qs.filter(status__in=('declined', 'canceled')).count(),
                'rembourses': qs.filter(status='refunded').count(),
            }
        except (AttributeError, KeyError):
            pass
        return r

    @admin.action(description="Exporter en CSV (Excel)")
    def exporter_csv(self, request, queryset):
        return export_csv(queryset, 'paiements')

    @admin.action(description="Supprimer (non payés seulement)", permissions=['delete'])
    def supprimer_non_payes(self, request, queryset):
        garde = queryset.filter(status__in=PAYES).count()
        if garde and not request.POST.get('post'):
            self.message_user(request, f"{garde} paiement(s) payé(s) ou remboursé(s) ne seront pas supprimés.",
                              messages.WARNING)
        return delete_selected(self, request, queryset.exclude(status__in=PAYES))

    @admin.action(description="Marquer « Remboursé » (paiements réussis)")
    def marquer_rembourse(self, request, queryset):
        n = queryset.filter(status='approved').update(status='refunded')
        self.message_user(request, f"{n} paiement(s) marqué(s) remboursé(s).")

    @admin.action(description="Marquer « Annulé » (non payés)")
    def marquer_annule(self, request, queryset):
        n = queryset.filter(status__in=('pending', 'declined')).update(status='canceled')
        self.message_user(request, f"{n} paiement(s) annulé(s).")

    @admin.action(description="Revérifier le statut chez FedaPay")
    def verify_with_fedapay(self, request, queryset):
        for p in queryset.filter(status='pending'):
            services.refresh(p)
        messages.success(request, "Statuts revérifiés auprès de FedaPay.")



from django import forms  # noqa: E402

from .models import MouvementSolde, Portefeuille  # noqa: E402


class MouvementInline(admin.TabularInline):
    model = MouvementSolde
    extra = 0
    can_delete = False
    fields = ['created_at', 'type', 'montant', 'solde_apres', 'motif', 'payment', 'par']
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Portefeuille)
class PortefeuilleAdmin(admin.ModelAdmin):
    list_display = ['user', 'solde_f', 'updated_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['user', 'solde', 'updated_at']
    inlines = [MouvementInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Solde", ordering='solde')
    def solde_f(self, pf):
        return francs(pf.solde)

    def changelist_view(self, request, extra_context=None):
        total = Portefeuille.objects.aggregate(s=Sum('solde'))['s'] or 0
        self.message_user(request, f"Total des soldes : {francs(total)} (argent dû en services aux clients).",
                          messages.INFO)
        return super().changelist_view(request, extra_context)


class AjustementForm(forms.ModelForm):
    utilisateur = forms.ModelChoiceField(queryset=None, label="Utilisateur")

    class Meta:
        model = MouvementSolde
        fields = ['montant', 'motif']

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        from django.contrib.auth import get_user_model
        self.fields['utilisateur'].queryset = get_user_model().objects.order_by('email')
        self.fields['motif'].required = True
        self.fields['montant'].help_text = "Positif = crédit, négatif = débit. Le solde ne peut pas devenir négatif."

    def clean(self):
        d = super().clean()
        u, m = d.get('utilisateur'), d.get('montant')
        if u is not None and m is not None:
            if m == 0:
                self.add_error('montant', "Montant non nul.")
            pf = Portefeuille.objects.filter(user=u).first()
            if (pf.solde if pf else 0) + m < 0:
                self.add_error('montant', f"Refusé : solde actuel {francs(pf.solde if pf else 0)}.")
        return d


@admin.register(MouvementSolde)
class MouvementSoldeAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'portefeuille', 'type', 'montant_f', 'solde_apres', 'motif', 'par']
    list_filter = ['type', 'created_at']
    search_fields = ['portefeuille__user__email', 'motif', 'payment__reference']
    date_hierarchy = 'created_at'

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = AjustementForm
        return super().get_form(request, obj, **kwargs)

    def get_fields(self, request, obj=None):
        return ['utilisateur', 'montant', 'motif'] if obj is None else \
            ['portefeuille', 'type', 'montant', 'solde_apres', 'payment', 'motif', 'par', 'created_at']

    def get_readonly_fields(self, request, obj=None):
        return [] if obj is None else ['portefeuille', 'type', 'montant', 'solde_apres', 'payment', 'motif', 'par',
                                       'created_at']

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return obj is None and request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Montant", ordering='montant')
    def montant_f(self, m):
        return f"{m.montant:+,} F".replace(',', '\u202f')

    def save_model(self, request, obj, form, change):
        from .solde import SoldeInsuffisant, ajuster
        try:
            m = ajuster(form.cleaned_data['utilisateur'], form.cleaned_data['montant'], form.cleaned_data['motif'],
                        request.user)
        except SoldeInsuffisant:
            self.message_user(request, "Refusé : le solde deviendrait négatif.", messages.ERROR)
            return
        obj.pk = m.pk
        self.message_user(request, f"Ajustement enregistré. Nouveau solde : {francs(m.solde_apres)}.")



from .models import CodePromo  # noqa: E402


class UtilisationsInline(admin.TabularInline):
    model = Payment
    fk_name = 'code_promo'
    extra = 0
    can_delete = False
    fields = ['reference', 'created_at', 'user', 'description', 'remise', 'amount', 'status']
    readonly_fields = fields
    verbose_name = "Utilisation"
    verbose_name_plural = "Utilisations (journal)"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CodePromo)
class CodePromoAdmin(admin.ModelAdmin):
    list_display = ['code', 'valeur_f', 'debut', 'fin', 'utilises', 'max_utilisations', 'actif']
    list_filter = ['actif', 'type']
    search_fields = ['code']
    autocomplete_fields = ['produits', 'concours', 'formations', 'evenements', 'vendeurs']
    inlines = [UtilisationsInline]
    fieldsets = (
        (None, {'fields': ('code', 'type', 'valeur', 'actif')}),
        ('Conditions', {'fields': ('debut', 'fin', 'minimum_achat', 'max_utilisations', 'max_par_personne')}),
        ('Limité à', {'fields': ('produits', 'concours', 'formations', 'evenements', 'vendeurs'),
                      'description': "Tout vide = valable sur tous les achats (sauf recharge du solde)."}),
    )

    @admin.display(description="Réduction")
    def valeur_f(self, c):
        return f"{c.valeur} %" if c.type == 'pct' else francs(c.valeur)

    @admin.display(description="Utilisé")
    def utilises(self, c):
        return c.paiements.filter(status='approved').count()
