from django.contrib import admin, messages
from django.db.models import Count, Q, Sum

from core.admin_retour import RetourMixin

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


from django import forms as _f  # noqa: E402


class _NouveauVendeur(_f.ModelForm):
    email = _f.EmailField(label="E-mail du vendeur", help_text="Son identifiant de connexion.")
    duree = _f.ChoiceField(label="Durée de l'accès", initial='3', widget=_f.RadioSelect, required=False,
                           choices=[('1', "1 mois"), ('3', "3 mois"), ('6', "6 mois"), ('12', "1 an"),
                                    ('illimite', "Sans limite"), ('date', "Date libre")])
    date_fin = _f.DateField(label="Date de fin (si « Date libre »)", required=False,
                            widget=_f.DateInput(attrs={'type': 'date'}))

    def clean(self):
        d = super().clean()
        if d.get('duree') == 'date' and not d.get('date_fin'):
            self.add_error('date_fin', "Choisissez la date de fin.")
        return d

    class Meta:
        model = Vendeur
        fields = ['boutique', 'whatsapp', 'ville', 'commission_pct']

    def clean_whatsapp(self):
        from Repetiteurs.models import whatsapp_togo
        return whatsapp_togo(self.cleaned_data.get('whatsapp'))

    def clean_email(self):
        from django.contrib.auth import get_user_model
        e = self.cleaned_data['email'].strip().lower()
        u = get_user_model().objects.filter(email__iexact=e).first()
        if u and Vendeur.objects.filter(user=u).exists():
            raise _f.ValidationError("Ce compte a déjà un espace vendeur.")
        return e


class EtatVendeurFiltre(admin.SimpleListFilter):
    title, parameter_name = "Accès", 'acces'

    def lookups(self, request, model_admin):
        return [('actif', "Actif"), ('bientot', "Expire bientôt"), ('expire', "Expiré"), ('suspendu', "Suspendu"),
                ('attente', "En attente")]

    def queryset(self, request, qs):
        from datetime import timedelta
        from django.db.models import Q
        from django.utils import timezone
        t, val = timezone.localdate(), self.value()
        ok = Q(statut='valide') & (Q(fin_acces__isnull=True) | Q(fin_acces__gte=t))
        if val == 'actif':
            return qs.filter(ok)
        if val == 'bientot':
            return qs.filter(ok, fin_acces__lte=t + timedelta(days=7))
        if val == 'expire':
            return qs.filter(Q(statut='expire') | Q(statut='valide', fin_acces__lt=t))
        if val == 'suspendu':
            return qs.filter(statut='suspendu')
        if val == 'attente':
            return qs.filter(statut='en_attente')
        return qs


@admin.register(Vendeur)
class VendeurAdmin(RetourMixin, admin.ModelAdmin):
    list_display = ['fiche', 'etat_pilule', 'fin_acces', 'ville', 'ventes', 'du_f', 'reste_f']
    actions = ['suspendre', 'reactiver_1', 'reactiver_3', 'reactiver_6', 'reactiver_12', 'reactiver_illimite',
               'envoyer_les_acces', 'regenerer_lien']
    list_filter = [EtatVendeurFiltre, 'ville']
    search_fields = ['boutique', 'user__email', 'ville']
    autocomplete_fields = ['user']
    inlines = [ReversementInline]
    readonly_fields = ['chiffres', 'lien']
    fieldsets = (
        (None, {'fields': ('user', 'boutique', 'whatsapp', 'statut', 'lien')}),
        ("Période d'accès", {'fields': ('debut_acces', 'fin_acces'),
                             'description': "Fin vide = sans limite. À la date de fin, le compte passe en « Expiré » "
                                            "(rien n'est effacé)."}),
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
                'commission_pct', 'numero_reversement', 'chiffres', 'debut_acces', 'fin_acces']

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = _NouveauVendeur
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return ((None, {'fields': ('boutique', 'email', 'whatsapp', 'ville', 'commission_pct', 'duree', 'date_fin'),
                            'description': "Le vendeur reçoit par e-mail son lien d'espace et crée son mot de passe."}),)
        return super().get_fieldsets(request, obj)

    def get_inlines(self, request, obj):
        return [] if obj is None else super().get_inlines(request, obj)

    def save_model(self, request, obj, form, change):
        if not change:
            from django.contrib.auth import get_user_model
            from .espace import envoyer_acces
            User = get_user_model()
            e = form.cleaned_data['email']
            u = User.objects.filter(email__iexact=e).first()
            if not u:
                u = User.objects.create_user(email=e, password=None)
                u.set_unusable_password()
                u.save()
            obj.user, obj.statut = u, 'valide'
            from django.utils import timezone
            from .acces_vendeur import fin_pour
            obj.debut_acces = timezone.localdate()
            obj.fin_acces = fin_pour(form.cleaned_data.get('duree') or 'illimite', form.cleaned_data.get('date_fin'))
            super().save_model(request, obj, form, change)
            envoyer_acces(obj)
            num = request.GET.get('contact') or ''
            if num.isdigit():
                ContactVendeur.objects.filter(pk=int(num)).update(statut='compte_cree', vendeur=obj)
            self.message_user(request, "Espace créé : le lien a été envoyé au vendeur par e-mail.", messages.SUCCESS)
            return
        super().save_model(request, obj, form, change)

    @admin.display(description="Lien de l'espace")
    def lien(self, v):
        from django.utils.html import format_html
        if not v.pk:
            return '—'
        from .espace import _site
        url = _site() + v.lien_espace()
        return format_html('<code style="font-size:12px">{}</code> <button type="button" class="button" '
                           'onclick="navigator.clipboard.writeText(\'{}\');this.textContent=\'Copié\'">Copier le lien</button>',
                           url, url)

    @admin.action(description="Envoyer les accès (lien pour créer le mot de passe)")
    def envoyer_les_acces(self, request, queryset):
        from .espace import envoyer_acces
        for v in queryset:
            envoyer_acces(v)
        self.message_user(request, f"Accès envoyés à {queryset.count()} vendeur(s).", messages.SUCCESS)

    @admin.action(description="Régénérer le lien (l'ancien ne marche plus)")
    def regenerer_lien(self, request, queryset):
        from .models import _code_espace
        for v in queryset:
            v.code = _code_espace()
            v.save(update_fields=['code'])
        self.message_user(request, "Nouveau lien créé. Pensez à l'envoyer au vendeur.", messages.SUCCESS)

    list_display_links = None  # un clic ouvre la fiche du vendeur (détails + produits)

    @admin.display(description="Boutique", ordering='boutique')
    def fiche(self, v):
        from django.urls import reverse
        from django.utils.html import format_html
        return format_html('<a href="{}"><b>{}</b></a>', reverse('admin_fiche', args=['vendeurs', v.pk]), v.boutique)

    def retour_defaut(self, v):
        from django.urls import reverse
        return reverse('admin_fiche', args=['vendeurs', v.pk])

    @admin.display(description="Accès")
    def etat_pilule(self, v):
        from django.utils.html import format_html
        code, txt = v.etat
        c = {'actif': ('#E8F3EC', '#0F6B3E'), 'bientot': ('#FBF4DF', '#8A6A0E'), 'attente': ('#F0F1EF', '#6B746E')}.get(
            code, ('#FBE9E7', '#C0392B'))
        return format_html('<span style="background:{};color:{};padding:3px 10px;border-radius:999px;font-weight:700;'
                           'font-size:12px;white-space:nowrap">{}</span>', c[0], c[1], txt)

    @admin.action(description="Suspendre (rien n'est effacé)")
    def suspendre(self, request, queryset):
        from .acces_vendeur import suspendre
        for v in queryset:
            suspendre(v)
        self.message_user(request, f"{queryset.count()} vendeur(s) suspendu(s).", messages.SUCCESS)

    def _reactiver(self, request, queryset, duree):
        from .acces_vendeur import fin_pour, reactiver
        for v in queryset:
            reactiver(v, fin_pour(duree))
        self.message_user(request, f"{queryset.count()} vendeur(s) réactivé(s).", messages.SUCCESS)

    @admin.action(description="Réactiver pour 1 mois")
    def reactiver_1(self, request, queryset):
        self._reactiver(request, queryset, '1')

    @admin.action(description="Réactiver pour 3 mois")
    def reactiver_3(self, request, queryset):
        self._reactiver(request, queryset, '3')

    @admin.action(description="Réactiver pour 6 mois")
    def reactiver_6(self, request, queryset):
        self._reactiver(request, queryset, '6')

    @admin.action(description="Réactiver pour 1 an")
    def reactiver_12(self, request, queryset):
        self._reactiver(request, queryset, '12')

    @admin.action(description="Réactiver sans limite")
    def reactiver_illimite(self, request, queryset):
        self._reactiver(request, queryset, 'illimite')

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


# ── Demandes de contact (page « Vendre sur Lantante ») ──
from .models import ContactVendeur  # noqa: E402


@admin.register(ContactVendeur)
class ContactVendeurAdmin(admin.ModelAdmin):
    list_display = ['boutique', 'nom', 'statut_pilule', 'categorie', 'ville', 'tel', 'created_at', 'actions_rapides']
    list_filter = ['statut', 'categorie', 'ville']
    search_fields = ['boutique', 'nom', 'telephone', 'email', 'ville']
    readonly_fields = ['created_at', 'boutons']
    actions = ['marquer_contactee', 'marquer_refusee']
    fieldsets = (
        (None, {'fields': ('boutons', 'statut', 'boutique', 'nom', 'telephone', 'email', 'ville', 'categorie', 'message')}),
        ("Suivi", {'fields': ('vendeur', 'note', 'created_at')}),
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description="Statut", ordering='statut')
    def statut_pilule(self, c):
        from django.utils.html import format_html
        coul = {'nouvelle': ('#FBF4DF', '#8A6A0E'), 'contactee': ('#E8F0FB', '#2457A6'),
                'compte_cree': ('#E8F3EC', '#0F6B3E'), 'refusee': ('#FBE9E7', '#C0392B')}[c.statut]
        return format_html('<span style="background:{};color:{};padding:3px 10px;border-radius:999px;font-weight:700;'
                           'font-size:12px;white-space:nowrap">{}</span>', coul[0], coul[1], c.get_statut_display())

    @admin.display(description="Téléphone")
    def tel(self, c):
        return f"+{c.telephone}" if c.telephone.isdigit() else c.telephone

    def _creer_url(self, c):
        from urllib.parse import urlencode
        from django.urls import reverse
        return reverse('admin:Marche_vendeur_add') + '?' + urlencode(
            {'boutique': c.boutique, 'email': c.email, 'whatsapp': c.telephone, 'ville': c.ville, 'contact': c.pk})

    @admin.display(description="")
    def actions_rapides(self, c):
        from django.utils.html import format_html
        return format_html('<a href="{}" target="_blank" rel="noopener" style="font-weight:700;color:#1FA855;margin-right:10px">WhatsApp</a>'
                           '<a href="{}" style="font-weight:700">Créer le vendeur</a>', c.lien_whatsapp(), self._creer_url(c))

    @admin.display(description="Actions")
    def boutons(self, c):
        from django.utils.html import format_html
        if not c.pk:
            return '—'
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;height:40px;padding:0 16px;'
            'border-radius:10px;background:#1FA855;color:#fff;font-weight:700;margin-right:8px;text-decoration:none">Répondre sur WhatsApp</a>'
            '<a href="{}" style="display:inline-flex;align-items:center;height:40px;padding:0 16px;border-radius:10px;background:#0F6B3E;'
            'color:#fff;font-weight:700;text-decoration:none">Créer le vendeur</a>', c.lien_whatsapp(), self._creer_url(c))

    @admin.action(description="Marquer « Contactée »")
    def marquer_contactee(self, request, queryset):
        n = queryset.filter(statut='nouvelle').update(statut='contactee')
        self.message_user(request, f"{n} demande(s) marquée(s) contactée(s).", messages.SUCCESS)

    @admin.action(description="Marquer « Refusée »")
    def marquer_refusee(self, request, queryset):
        n = queryset.update(statut='refusee')
        self.message_user(request, f"{n} demande(s) refusée(s).", messages.SUCCESS)
