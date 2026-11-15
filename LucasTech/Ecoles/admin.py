
from django import forms
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils import timezone

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
class EcoleAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type', 'ville', 'nb_filieres', 'publie']
    list_filter = ['type', 'publie', 'ville']
    search_fields = ['nom', 'ville']
    inlines = [PhotoInline, FiliereInline, NouveauteInline, MembreInline]
    form = EcoleForm
    fieldsets = [
        (None, {'fields': ['nom', 'type', 'cycles', 'ville', 'logo', 'couverture', 'description']}),
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


