import io

from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone

from .models import CYCLES, NouveauteEcole, Ecole, Filiere, InscriptionEcole, MembreEcole, PhotoEcole


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
    entetes = ['Date', 'École', 'Cycle', 'Classe / niveau', 'Série', 'Filière', 'Prénom', 'Nom', 'Téléphone', 'E-mail',
               'Message', 'Statut', 'Document']
    from django.conf import settings
    site = getattr(settings, 'SITE_URL', 'https://lantantetechnologie.com').rstrip('/')
    ws.append(entetes)
    for c in ws[1]:
        c.font = Font(bold=True)
    for i in queryset.select_related('ecole', 'filiere'):
        doc = f"{site}{reverse('ecole_document', args=[i.pk])}" if i.document else ''
        ws.append([timezone.localtime(i.created_at).strftime('%d/%m/%Y %H:%M'), i.ecole.nom, i.get_cycle_display(),
                   i.classe or i.niveau_etudes or i.niveau_actuel, i.serie_bac, i.filiere.nom if i.filiere_id else '',
                   i.prenom, i.nom, i.telephone, i.email, i.message, i.get_statut_display(), doc])
        if doc:
            ws.cell(row=ws.max_row, column=len(entetes)).hyperlink = doc
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = min(40, max(12, max(len(str(c.value or '')) for c in col) + 2))
    buf = io.BytesIO()
    wb.save(buf)
    r = HttpResponse(buf.getvalue(),
                     content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    r['Content-Disposition'] = f'attachment; filename="{nom}-{timezone.localdate():%Y-%m-%d}.xlsx"'
    return r


class NouveauteInline(admin.StackedInline):
    model = NouveauteEcole
    extra = 0
    fields = [('titre', 'date', 'publie'), 'image', 'texte']


class EcoleForm(forms.ModelForm):
    cycles = forms.MultipleChoiceField(label="Cycles", choices=CYCLES, required=False,
                                       widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Ecole
        fields = '__all__'


class PhotoInline(admin.TabularInline):
    model = PhotoEcole
    extra = 1


class FiliereInline(admin.StackedInline):
    model = Filiere
    extra = 0
    fields = [('cycle', 'nom'), ('niveau', 'duree'), ('frais', 'ouverte', 'ordre'), 'image', 'description']


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
    inlines = [NouveauteInline, FiliereInline, PhotoInline, MembreInline]
    form = EcoleForm
    readonly_fields = ['resume']
    fieldsets = [
        (None, {'fields': ['resume', 'nom', 'type', 'cycles', 'ville', 'logo', 'couverture', 'description']}),
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
    list_display = ['date', 'prenom', 'nom', 'telephone', 'ecole', 'cycle', 'classe_niveau', 'filiere', 'doc', 'statut']
    readonly_fields = ['doc']
    list_filter = ['statut', 'cycle', ('ecole', admin.RelatedOnlyFieldListFilter), 'created_at']
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

    @admin.display(description="Classe / niveau")
    def classe_niveau(self, i):
        return ' '.join(x for x in (i.classe or i.niveau_etudes, i.serie_bac and f"(série {i.serie_bac})") if x)

    @admin.display(description="Document")
    def doc(self, i):
        if not i.document:
            return '—'
        return format_html('<a href="{}" target="_blank">Ouvrir</a>', reverse('ecole_document', args=[i.pk]))

    @admin.action(description="Exporter en Excel")
    def exporter_excel(self, request, queryset):
        return export_excel(queryset, 'inscriptions')
