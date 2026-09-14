import csv

from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import (
    PublicationCategory, Publication, PublicationImage, PublicationVideo,
    EventRegistration,
)


# ─────────────────────────────
# Images / vidéos inline
# ─────────────────────────────
class PublicationImageInline(admin.TabularInline):
    model  = PublicationImage
    extra  = 3
    fields = ['image', 'caption', 'order']


class PublicationVideoInline(admin.TabularInline):
    model  = PublicationVideo
    extra  = 1
    fields = ['video', 'caption', 'order']


# ─────────────────────────────
# Catégorie
# ─────────────────────────────
@admin.register(PublicationCategory)
class PublicationCategoryAdmin(admin.ModelAdmin):
    list_display        = ['name', 'icon', 'order']
    prepopulated_fields = {'slug': ('name',)}
    ordering            = ['order', 'name']


# ─────────────────────────────
# 📤 Export CSV des inscriptions
# ─────────────────────────────
@admin.action(description="Exporter la sélection en CSV (Excel)")
def export_registrations_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="inscriptions_evenements.csv"'
    response.write('﻿')  # BOM pour qu'Excel affiche correctement les accents

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Événement', 'Prénom', 'Nom', 'Email', 'Téléphone', 'Pays', 'Message', 'Date'])
    for reg in queryset.select_related('publication'):
        writer.writerow([
            reg.publication.title, reg.first_name, reg.last_name, reg.email,
            reg.phone, reg.country, reg.message,
            reg.created_at.strftime('%d/%m/%Y %H:%M'),
        ])
    return response


# ─────────────────────────────
# Publication
# ─────────────────────────────
@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display   = ['title', 'author', 'category', 'publication_type', 'is_published', 'is_featured', 'views_count', 'created_at']
    list_filter    = ['is_published', 'is_featured', 'publication_type', 'category']
    list_editable  = ['is_published', 'is_featured']
    search_fields  = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}
    inlines        = [PublicationImageInline, PublicationVideoInline]

    # ── Utilise CKEditor si disponible, sinon Textarea large ──
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'content':
            try:
                from ckeditor.widgets import CKEditorWidget
                kwargs['widget'] = CKEditorWidget(config_name='default')
            except ImportError:
                from django.forms import Textarea
                kwargs['widget'] = Textarea(attrs={'rows': 30, 'style': 'width:100%;font-size:14px;'})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_queryset(self, request):
        # Tout admin ayant accès à ce module voit toutes les publications
        # (et pas seulement les siennes) — Django gère déjà les permissions
        # d'accès au module via is_staff / les permissions du modèle.
        return super().get_queryset(request)

    def save_model(self, request, obj, form, change):
        # Ne force l'auteur que si l'admin n'a pas explicitement choisi
        # (et jamais pour un superuser, qui doit pouvoir publier au nom
        # de n'importe quel auteur).
        if not obj.pk and not request.user.is_superuser:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" style="height:50px;border-radius:6px;">', obj.cover_image.url)
        return "—"
    cover_preview.short_description = "Couverture"

    fieldsets = (
        ('Informations principales', {
            'fields': ('title', 'slug', 'category', 'author')
        }),
        ('Type de publication', {
            'fields': ('publication_type',),
            'description': (
                "« Article / Actualité » : un article classique. "
                "« Événement » : affiche les infos de date/lieu et permet aux visiteurs "
                "de s'inscrire via un formulaire (les inscrits sont exportables en CSV/Excel "
                "depuis l'onglet « Inscriptions aux événements »)."
            ),
        }),
        ('Détails de l\'événement (si type = Événement)', {
            'fields': ('event_date', 'event_location', 'registration_open'),
            'classes': ('collapse',),
        }),
        ('Médias de couverture', {
            'fields': ('cover_image', 'cover_video'),
            'classes': ('collapse',),
        }),
        ('Contenu', {
            'fields': ('content',),
        }),
        ('Publication', {
            'fields': ('is_published', 'is_featured'),
        }),
    )


# ─────────────────────────────
# Inscriptions aux événements
# ─────────────────────────────
@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display    = ['first_name', 'last_name', 'publication', 'email', 'phone', 'country', 'created_at']
    list_filter     = ['publication']
    search_fields   = ['first_name', 'last_name', 'email', 'phone']
    readonly_fields = ['first_name', 'last_name', 'email', 'phone', 'country', 'message', 'publication', 'created_at']
    actions         = [export_registrations_csv]
