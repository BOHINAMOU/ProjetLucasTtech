from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from Publications.admin import MarkReadOnOpenMixin
from .models import (
    Profile, Skill, Project, ProjectImage, Service, Certificate, Collaborator,
    Experience, Engagement, Stat, ContactMessage,
)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Une seule fiche : on ouvre directement le formulaire."""
    fieldsets = (
        ("En haut de la page", {'fields': ('full_name', 'title', 'tagline', 'photo', 'intro')}),
        ("Qui est Bohinamou ?", {'fields': ('bio',)}),
        ("Contact et disponibilité", {'fields': ('availability', 'city', 'email', 'phone', 'whatsapp', 'cv')}),
        ("Réseaux sociaux et site", {'fields': ('website', 'linkedin', 'github', 'facebook', 'instagram', 'tiktok', 'youtube', 'x_twitter')}),
    )

    def has_add_permission(self, request):
        return not Profile.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        return redirect(reverse('admin:Portfolio_profile_change', args=[Profile.load().pk]))


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('apercu', 'name', 'category', 'level', 'order', 'is_active')
    list_display_links = ('name',)
    list_editable = ('order', 'is_active')
    list_filter = ('category', 'level', 'is_active')
    search_fields = ('name', 'description')

    @admin.display(description="Logo")
    def apercu(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="height:26px">', obj.logo.url)
        if obj.icon_class:
            return format_html('<i class="{}" style="font-size:24px"></i>', obj.icon_class)
        return '—'


class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 1


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'client', 'year', 'order', 'is_published')
    list_editable = ('order', 'is_published')
    list_filter = ('is_published',)
    search_fields = ('title', 'client', 'summary')
    filter_horizontal = ('skills',)
    inlines = [ProjectImageInline]
    fieldsets = (
        (None, {'fields': ('title', 'client', 'year', 'summary', 'image', 'link', 'is_published', 'order')}),
        ("Détails", {'fields': ('description', 'role', 'skills')}),
    )


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'is_active')
    list_editable = ('order', 'is_active')


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'organization', 'date', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter = ('kind', 'is_active')
    search_fields = ('title', 'organization')


@admin.register(Collaborator)
class CollaboratorAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'role', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('full_name', 'role', 'expertise')


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'organization', 'period', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter = ('kind',)


@admin.register(Engagement)
class EngagementAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'role', 'period', 'order', 'is_active')
    list_editable = ('order', 'is_active')


@admin.register(Stat)
class StatAdmin(admin.ModelAdmin):
    list_display = ('value', 'label', 'order', 'is_active')
    list_editable = ('order', 'is_active')


@admin.register(ContactMessage)
class ContactMessageAdmin(MarkReadOnOpenMixin, admin.ModelAdmin):
    list_display = ('lu', 'name', 'contact', 'extrait', 'created_at')
    list_display_links = ('name',)
    list_filter = ('is_read',)
    actions = ['mark_read', 'mark_unread']
    readonly_fields = ('name', 'contact', 'message', 'created_at')

    @admin.display(description="Lu", boolean=True, ordering='is_read')
    def lu(self, obj):
        return obj.is_read

    @admin.display(description="Message")
    def extrait(self, obj):
        return obj.message[:80]

    def has_add_permission(self, request):
        return False
