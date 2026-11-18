
from django import forms
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils import timezone

from core.admin_retour import RetourMixin

from .models import CYCLES, NouveauteEcole, Ecole, Filiere, MembreEcole, PhotoEcole


def mes_ecoles(user):
    if user.is_superuser:
        return Ecole.objects.all()
    return Ecole.objects.filter(membres__user=user).distinct()


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
    fields = [('cycle', 'nom'), ('niveau', 'duree', 'frais', 'ordre'), 'resume', 'image', 'description', 'debouches',
              'conditions']


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
class EcoleAdmin(RetourMixin, admin.ModelAdmin):
    list_display = ['fiche', 'type', 'ville', 'nb_filieres', 'publie']
    list_filter = ['type', 'publie', 'ville']
    search_fields = ['nom', 'ville']
    list_display_links = None  # un clic ouvre la fiche de l'école (détails + filières)
    inlines = [PhotoInline, NouveauteInline, MembreInline]  # les filières se gèrent depuis la fiche
    form = EcoleForm
    fieldsets = [
        (None, {'fields': ['nom', 'alias', 'type', 'cycles', 'ville', 'logo', 'couverture', 'description']}),
        ("Contact", {'fields': [('telephone', 'whatsapp'), ('email', 'site_web'), 'adresse']}),
        ("Inscription", {'fields': ['lien_inscription'],
                         'description': "Le bouton « S'inscrire » ouvre ce lien (sinon le site web)."}),
        ("Publication", {'fields': [('publie', 'ordre')]}),
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

    @admin.display(description="École", ordering='nom')
    def fiche(self, e):
        return format_html('<a href="{}"><b>{}</b></a>', reverse('admin_fiche', args=['ecoles', e.pk]), e.nom)

    def retour_defaut(self, e):
        return reverse('admin_fiche', args=['ecoles', e.pk])


@admin.register(Filiere)
class FiliereAdmin(RetourMixin, admin.ModelAdmin):
    list_display = ['nom', 'ecole', 'cycle', 'niveau', 'frais', 'ordre']
    list_filter = ['cycle']
    search_fields = ['nom', 'ecole__nom']
    fields = ['ecole', ('cycle', 'nom'), ('niveau', 'duree', 'frais', 'ordre'), 'resume', 'image', 'description',
              'debouches', 'conditions']

    def get_queryset(self, request):
        return super().get_queryset(request).filter(ecole__in=mes_ecoles(request.user))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'ecole':
            kwargs['queryset'] = mes_ecoles(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def retour_defaut(self, f):
        return reverse('admin_fiche', args=['ecoles', f.ecole_id])


