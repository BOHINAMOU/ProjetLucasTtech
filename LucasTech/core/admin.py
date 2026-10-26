from django.contrib import admin, messages
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.html import format_html
from Publications.admin import MarkReadOnOpenMixin
from .models import (
    Partner, PartnerCategory, PartnerApplication, MonetizationRequest, Project, TeamMember,
    HeroSlide, NewsTickerItem, SiteSettings,
)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    # Singleton : une seule ligne de réglages, pas d'ajout ni de suppression.
    fieldsets = (
        ('Contact', {
            'fields': ('email', 'email_2', 'whatsapp_1', 'whatsapp_2'),
        }),
        ('Paiements (publications des entreprises)', {
            'fields': ('payment_flooz', 'payment_tmoney'),
            'description': "Numéros Mobile Money affichés aux entreprises quand elles paient. Laissez vide pour leur demander de vous contacter sur WhatsApp.",
        }),
        ('Prix des publications', {
            'fields': ('publication_price',),
            'description': "Prix unique d'une publication (actualité, offre d'emploi, publicité) : 2 500 FCFA par défaut. "
                           "Il s'applique à tous les tarifs de publication, pour les entreprises et les particuliers.",
        }),
        ('Réseaux sociaux', {
            'fields': ('facebook_url', 'instagram_url', 'tiktok_url',
                       'youtube_url', 'telegram_url', 'twitter_url'),
            'description': "Laissez un champ vide pour masquer ce réseau dans le pied de page.",
        }),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Redirige directement vers l'unique fiche de réglages.
        obj = SiteSettings.load()
        from django.shortcuts import redirect
        return redirect('admin:core_sitesettings_change', obj.pk)


@admin.register(PartnerCategory)
class PartnerCategoryAdmin(admin.ModelAdmin):
    list_display        = ('name', 'icon', 'order')
    prepopulated_fields = {'slug': ('name',)}
    ordering             = ('order', 'name')


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display   = ('name', 'category', 'country', 'is_active', 'order')
    list_editable   = ('is_active', 'order')
    list_filter     = ('category', 'is_active')
    search_fields   = ('name', 'domain', 'description')
    fieldsets = (
        ('Informations principales', {
            'fields': ('name', 'category', 'logo', 'country', 'is_active', 'order'),
        }),
        ('À propos', {
            'fields': ('domain', 'description', 'achievements'),
        }),
        ('Contact', {
            'fields': ('website', 'email', 'phone', 'whatsapp'),
        }),
    )


@admin.register(PartnerApplication)
class PartnerApplicationAdmin(admin.ModelAdmin):
    list_display    = ('full_name', 'email', 'country', 'status', 'created_at')
    list_filter     = ('status', 'country')
    search_fields   = ('full_name', 'email', 'description')
    readonly_fields = ('created_at', 'reviewed_at', 'published_partner')
    fieldsets = (
        ('Candidat', {
            'fields': ('full_name', 'email', 'whatsapp', 'country', 'phone_code', 'phone_number', 'logo'),
        }),
        ('Présentation', {
            'fields': ('description',),
        }),
        ('Traitement', {
            'fields': ('status', 'admin_note', 'published_partner', 'created_at', 'reviewed_at'),
        }),
    )
    actions = ['publish_to_site', 'reject_application']

    @admin.action(description="✅ Accepter et publier sur le site")
    def publish_to_site(self, request, queryset):
        published = 0
        for application in queryset.exclude(status='approved'):
            partner = Partner(
                name=application.full_name,
                country=application.country,
                email=application.email,
                whatsapp=application.whatsapp,
                phone=application.full_phone,
                description=application.description,
                is_active=True,
            )
            if application.logo:
                application.logo.open('rb')
                data = application.logo.read()
                application.logo.close()
                partner.logo = ContentFile(data, name=application.logo.name.split('/')[-1])
            partner.save()

            application.status = 'approved'
            application.reviewed_at = timezone.now()
            application.published_partner = partner
            application.save()
            published += 1

        if published:
            self.message_user(request, f"{published} candidature(s) publiée(s) sur le site.")
        else:
            self.message_user(request, "Aucune candidature à publier (déjà publiées ?).", level=messages.WARNING)

    @admin.action(description="❌ Rejeter la candidature")
    def reject_application(self, request, queryset):
        updated = queryset.exclude(status='rejected').update(status='rejected', reviewed_at=timezone.now())
        self.message_user(request, f"{updated} candidature(s) rejetée(s).")


@admin.register(MonetizationRequest)
class MonetizationRequestAdmin(MarkReadOnOpenMixin, admin.ModelAdmin):
    list_display    = ('lu', 'full_name', 'country', 'telephone', 'platforms', 'status', 'created_at')
    list_display_links = ('full_name',)
    list_filter     = ('is_read', 'status', 'country')
    list_editable   = ('status',)
    search_fields   = ('first_name', 'last_name', 'phone_number', 'address', 'platforms', 'message')
    actions         = ['mark_read', 'mark_unread']
    readonly_fields = ('first_name', 'last_name', 'address', 'country', 'phone_code', 'phone_number', 'platforms',
                       'message', 'whatsapp_link', 'created_at')
    fieldsets = (
        ('Demandeur', {'fields': ('first_name', 'last_name', 'address', 'country', 'phone_code', 'phone_number', 'whatsapp_link')}),
        ('Demande', {'fields': ('platforms', 'message', 'created_at')}),
        ('Suivi', {'fields': ('status', 'is_read', 'admin_note')}),
    )

    @admin.display(description="Lu", boolean=True, ordering='is_read')
    def lu(self, obj):
        return obj.is_read

    @admin.display(description="Téléphone")
    def telephone(self, obj):
        return obj.full_phone

    @admin.display(description="Écrire sur WhatsApp")
    def whatsapp_link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">Ouvrir la conversation WhatsApp avec {}</a>', obj.whatsapp_url, obj.full_phone)

    def has_add_permission(self, request):
        return False


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('tag', 'title', 'link_url', 'order', 'is_active')
    list_editable = ('order', 'is_active')


@admin.register(NewsTickerItem)
class NewsTickerItemAdmin(admin.ModelAdmin):
    list_display = ('label', 'message', 'link_url', 'order', 'is_active')
    list_editable = ('order', 'is_active')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'client', 'year', 'order')
    list_editable = ('order',)
    search_fields = ('title', 'client', 'description')


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'is_founder', 'order')
    list_editable = ('order',)
    list_filter = ('is_founder',)
    search_fields = ('name', 'role')

# ─────────────────────────────
# 🏠 Accueil de l'administration : tableau de bord (chiffres, actions rapides, commentaires lus / non lus)
# ─────────────────────────────
from .dashboard import build as _build_dashboard  # noqa: E402

_original_index = admin.site.index


def _dashboard_index(request, extra_context=None):
    extra = dict(extra_context or {})
    extra['dash'] = _build_dashboard(request)
    return _original_index(request, extra)


admin.site.index = _dashboard_index
