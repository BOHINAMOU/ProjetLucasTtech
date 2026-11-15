import io

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone

from .models import Ecole, Filiere, InscriptionEcole, MembreEcole, PhotoEcole


def mes_ecoles(user):
    if user.is_superuser:
        return Ecole.objects.all()
    return Ecole.objects.filter(membres__user=user).distinct()


def export_excel(queryset, nom):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = 'Inscriptions'
    entetes = ['Date', 'École', 'Filière', 'Prénom', 'Nom', 'Téléphone', 'E-mail', 'Niveau actuel', 'Message', 'Statut']
    ws.append(entetes)
    for c in ws[1]:
        c.font = Font(bold=True)
    for i in queryset.select_related('ecole', 'filiere'):
        ws.append([timezone.localtime(i.created_at).strftime('%d/%m/%Y %H:%M'), i.ecole.nom,
                   i.filiere.nom if i.filiere_id else '', i.prenom, i.nom, i.telephone, i.email, i.niveau_actuel,
                   i.message, i.get_statut_display()])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(40, max(12, max(len(str(c.value or '')) for c in col) + 2))
    buf = io.BytesIO()
    wb.save(buf)
    r = HttpResponse(buf.getvalue(),
                     content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    r['Content-Disposition'] = f'attachment; filename="{nom}-{timezone.localdate():%Y-%m-%d}.xlsx"'
    return r


class PhotoInline(admin.TabularInline):
    model = PhotoEcole
    extra = 1


class FiliereInline(admin.StackedInline):
    model = Filiere
    extra = 0
    fields = [('nom', 'niveau', 'duree'), ('frais', 'ouverte', 'ordre'), 'image', 'description']


class MembreInline(admin.TabularInline):
    model = MembreEcole
    extra = 1
    autocomplete_fields = ['user']

    def _responsable(self, request, obj):
        return request.user.is_superuser or (obj is not None and obj.membres.filter(
            user=request.user, role='proprietaire').exists())

    def has_add_permission(self, request, obj=None):
        return self._responsable(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._responsable(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._responsable(request, obj)


@admin.register(Ecole)
class EcoleAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type', 'ville', 'nb_filieres', 'nb_inscriptions', 'nouvelles', 'publie']
    list_filter = ['type', 'publie', 'ville']
    search_fields = ['nom', 'ville']
    inlines = [FiliereInline, PhotoInline, MembreInline]
    readonly_fields = ['resume']
    fieldsets = [
        (None, {'fields': ['resume', 'nom', 'type', 'ville', 'logo', 'couverture', 'description']}),
        ("Contact", {'fields': [('telephone', 'whatsapp'), ('email', 'site_web')]}),
        ("Publication", {'fields': [('publie', 'inscriptions_ouvertes', 'ordre')]}),
    ]

    def get_queryset(self, request):
        return mes_ecoles(request.user)

    def has_add_permission(self, request):
        return request.user.is_superuser  # l'équipe Lantante crée l'école, puis donne l'accès

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description="Filières")
    def nb_filieres(self, e):
        return e.filieres.count()

    @admin.display(description="Inscriptions")
    def nb_inscriptions(self, e):
        return e.inscriptions.count()

    @admin.display(description="Nouvelles")
    def nouvelles(self, e):
        return e.inscriptions.filter(statut='nouvelle').count()

    @admin.display(description="Résumé")
    def resume(self, e):
        from django.urls import reverse
        from django.utils.html import format_html
        if not e.pk:
            return '—'
        url = reverse('admin:Ecoles_inscriptionecole_changelist') + f'?ecole__id__exact={e.pk}'
        return format_html('<b style="font-size:18px;color:#0B7A4B">{}</b> inscription(s) · <b>{}</b> nouvelle(s) · '
                           '{} filière(s) <br><a class="button" style="margin-top:8px;display:inline-block" href="{}">'
                           'Voir les inscriptions (Excel)</a>', e.inscriptions.count(),
                           e.inscriptions.filter(statut='nouvelle').count(), e.filieres.count(), url)


@admin.register(InscriptionEcole)
class InscriptionEcoleAdmin(admin.ModelAdmin):
    list_display = ['date', 'prenom', 'nom', 'telephone', 'ecole', 'filiere', 'statut']
    list_filter = ['statut', ('ecole', admin.RelatedOnlyFieldListFilter), 'created_at']
    search_fields = ['nom', 'prenom', 'telephone', 'email']
    list_editable = ['statut']
    actions = ['exporter_excel']
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('ecole', 'filiere')
        return qs if request.user.is_superuser else qs.filter(ecole__in=mes_ecoles(request.user))

    def has_add_permission(self, request):
        return False

    @admin.display(description="Date", ordering='created_at')
    def date(self, i):
        return timezone.localtime(i.created_at).strftime('%d/%m/%Y %H:%M')

    @admin.action(description="Exporter en Excel")
    def exporter_excel(self, request, queryset):
        return export_excel(queryset, 'inscriptions')
