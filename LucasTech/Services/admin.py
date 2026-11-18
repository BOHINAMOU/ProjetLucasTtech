from django import forms
from django.contrib import admin
from .models import ServiceCategory, Service, ServiceContact


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'parent', 'icone_appli', 'couleur', 'order']
    list_editable = ['icone_appli', 'couleur', 'order']
    list_filter = ['parent']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'name']


class ChampInscriptionInline(admin.TabularInline):
    from .models import ChampInscription as _C
    model = _C
    extra = 1
    fields = ['libelle', 'type', 'obligatoire', 'choix', 'ordre']


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display  = ['title', 'category', 'inscriptions_ouvertes', 'nb_inscriptions', 'clics_whatsapp', 'clics_support',
                     'is_featured', 'is_active']
    list_filter   = ['is_active', 'inscriptions_ouvertes', 'is_featured', 'category']
    inlines       = [ChampInscriptionInline]
    actions       = ['cloturer', 'ouvrir']

    @admin.display(description="Inscriptions")
    def nb_inscriptions(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        n = obj.inscriptions.count()
        url = reverse('admin:Services_inscriptionservice_changelist') + f'?service__id__exact={obj.pk}'
        return format_html('<a href="{}">{}</a>', url, n) if n else 0

    @admin.action(description="Clôturer les inscriptions")
    def cloturer(self, request, queryset):
        n = queryset.update(inscriptions_ouvertes=False)
        self.message_user(request, f"{n} service(s) clôturé(s).")

    @admin.action(description="Ouvrir les inscriptions")
    def ouvrir(self, request, queryset):
        n = queryset.update(inscriptions_ouvertes=True)
        self.message_user(request, f"{n} service(s) ouvert(s) aux inscriptions.")
    search_fields = ['title', 'description']
    list_editable = ['is_featured', 'is_active']
    exclude       = ['admin']

    def get_queryset(self, request):
        # L'équipe voit tout ; un délégué ne voit que les services qui lui sont confiés.
        from core.delegations import services_visibles
        return services_visibles(request.user, super().get_queryset(request))

    def has_add_permission(self, request):
        return request.user.is_superuser or super().has_add_permission(request) and not request.user.delegations.exists()

    def save_model(self, request, obj, form, change):
        # L'admin responsable n'est jamais choisi dans le formulaire :
        # c'est toujours la personne connectée.
        if not obj.pk:
            obj.admin = request.user
        super().save_model(request, obj, form, change)


@admin.register(ServiceContact)
class ServiceContactAdmin(admin.ModelAdmin):
    list_display  = ['name', 'phone', 'service', 'created_at', 'is_read']
    list_filter   = ['is_read', 'service']
    list_editable = ['is_read']
    readonly_fields = ['name', 'phone', 'message', 'service', 'user', 'created_at']


from .models import InscriptionService  # noqa: E402


@admin.register(InscriptionService)
class InscriptionServiceAdmin(admin.ModelAdmin):
    list_display = ['date', 'service', 'resume', 'compte', 'statut']
    list_filter = ['statut', ('service', admin.RelatedOnlyFieldListFilter), 'created_at']
    list_editable = ['statut']
    search_fields = ['reponses', 'user__email', 'service__title']
    readonly_fields = ['service', 'user', 'reponses', 'created_at']
    actions = ['exporter_excel']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        from core.delegations import services_visibles
        from .models import Service
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(
            service__in=services_visibles(request.user, Service.objects.all()))

    @admin.display(description="Date", ordering='created_at')
    def date(self, i):
        from django.utils import timezone
        return timezone.localtime(i.created_at).strftime('%d/%m/%Y %H:%M')

    @admin.display(description="Réponses")
    def resume(self, i):
        return ' · '.join(str(v) for v in list((i.reponses or {}).values())[:3])

    @admin.display(description="Compte")
    def compte(self, i):
        return i.user.email if i.user_id else '—'

    @admin.action(description="Exporter en Excel (une feuille par service)")
    def exporter_excel(self, request, queryset):
        import io
        from django.http import HttpResponse
        from django.utils import timezone
        from openpyxl import Workbook
        from openpyxl.styles import Font
        wb = Workbook()
        wb.remove(wb.active)
        par_service = {}
        for i in queryset.select_related('service', 'user').order_by('service_id', 'created_at'):
            par_service.setdefault(i.service, []).append(i)
        for service, lignes in par_service.items():
            ws = wb.create_sheet((service.title[:28] or 'Service').replace('/', '-').replace(':', ' '))
            libelles = [c.libelle for c in service.champs.all()]
            for i in lignes:  # champs supprimés depuis : on garde les anciennes réponses
                libelles += [k for k in (i.reponses or {}) if k not in libelles]
            ws.append(['Date', 'Compte', *libelles, 'Statut'])
            for c in ws[1]:
                c.font = Font(bold=True)
            for i in lignes:
                ws.append([timezone.localtime(i.created_at).strftime('%d/%m/%Y %H:%M'),
                           i.user.email if i.user_id else '', *[(i.reponses or {}).get(k, '') for k in libelles],
                           i.get_statut_display()])
        if not par_service:
            wb.create_sheet('Inscriptions')
        buf = io.BytesIO()
        wb.save(buf)
        r = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        r['Content-Disposition'] = f'attachment; filename="inscriptions-services-{timezone.localdate():%Y-%m-%d}.xlsx"'
        return r



from .models import ICONES_APPLI, Service, ServiceCategory  # noqa: E402
from .widgets import ChoixIcone  # noqa: E402


def _avec_icones(admin_cls, modele, vide):
    class Form(forms.ModelForm):
        class Meta:
            model = modele
            fields = '__all__'
            widgets = {'icone_appli': ChoixIcone(choices=([('', 'Icône de la catégorie')] if vide else []) + ICONES_APPLI)}
    admin_cls.form = Form


_avec_icones(ServiceCategoryAdmin, ServiceCategory, False)
_avec_icones(ServiceAdmin, Service, True)
ServiceCategoryAdmin.list_editable = ['order']  # l'icône se choisit dans la fiche (grille visuelle)
