from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import (
    Appointment, Application, CandidateProfile, Conversation, EmployerProfile,
    FeedComment, FeedPost, JobOffer, Message, Notification, Placement,
    ProfileRevision, Skill, StaffingRequest,
)
from .services import notify, suggest_candidates


# ─────────────────────────────
# 🔎 Suggestions automatiques de candidats
# ─────────────────────────────
class SuggestionsMixin:
    """Ajoute à une offre / demande une page « Candidats suggérés » (domaine, compétences, ville)."""

    def get_urls(self):
        name = f"emploi_{self.model._meta.model_name}_suggestions"
        return [
            path('<int:pk>/suggestions/', self.admin_site.admin_view(self.suggestions_view), name=name),
        ] + super().get_urls()

    def suggestions_view(self, request, pk):
        target = get_object_or_404(self.model, pk=pk)
        if not self.has_change_permission(request, target):
            raise PermissionDenied
        is_offer = isinstance(target, JobOffer)

        if request.method == 'POST':
            cand = get_object_or_404(CandidateProfile, pk=request.POST.get('candidate'))
            application, created = Application.objects.get_or_create(
                candidate=cand,
                **({'offer': target} if is_offer else {'request': target}),
                defaults={'origin': 'lantante', 'status': 'shortlisted'},
            )
            if created:
                notify(cand.user, f"Lantante vous propose une opportunité : {target.title}",
                       target.get_absolute_url() if is_offer else '/emploi/mon-espace/')
                if not is_offer and target.status == 'new':
                    target.status = 'proposed'
                    target.save(update_fields=['status'])
                messages.success(request, f"{cand.name} a été proposé(e) et notifié(e).")
            else:
                messages.info(request, f"{cand.name} est déjà lié(e) à cette demande.")
            return redirect(request.path)

        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': f"Candidats suggérés — {target.title}",
            'target': target,
            'results': suggest_candidates(target),
            'back_url': reverse(f'admin:Emploi_{self.model._meta.model_name}_change', args=[target.pk]),
        }
        return render(request, 'admin/emploi/suggestions.html', context)

    @admin.display(description="Candidats suggérés")
    def suggestions_link(self, obj):
        url = reverse(f'admin:emploi_{self.model._meta.model_name}_suggestions', args=[obj.pk])
        return format_html('<a class="btn btn-sm btn-primary" href="{}"><i class="fas fa-magic"></i> Voir</a>', url)


# ─────────────────────────────
# 🧰 Compétences
# ─────────────────────────────
@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


# ─────────────────────────────
# 👤 Candidats
# ─────────────────────────────
class ProfileRevisionInline(admin.TabularInline):
    model = ProfileRevision
    extra = 0
    can_delete = False
    fields = ('created_at', 'changed_fields', 'data')
    readonly_fields = ('created_at', 'changed_fields', 'data')

    def has_add_permission(self, request, obj=None):
        return False


class CandidateApplicationInline(admin.TabularInline):
    model = Application
    extra = 0
    fields = ('offer', 'request', 'status', 'origin', 'created_at')
    readonly_fields = ('created_at',)
    show_change_link = True


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'headline', 'domain', 'city', 'experience_years', 'available',
                    'share_with_recruiters', 'is_published', 'updated_at')
    list_filter = ('domain', 'available', 'is_published', 'share_with_recruiters', 'city')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'headline', 'city', 'skills__name')
    filter_horizontal = ('skills',)
    readonly_fields = ('cv_link', 'contact_info', 'created_at', 'updated_at')
    autocomplete_fields = ('user',)
    inlines = [CandidateApplicationInline, ProfileRevisionInline]
    fieldsets = (
        ("Compte", {'fields': ('user', 'contact_info')}),
        ("Profil", {'fields': ('headline', 'domain', 'skills', 'city', 'bio', 'experience_years',
                               'education_level', 'contract_wanted', 'available')}),
        ("CV et contact (privés)", {'fields': ('phone', 'cv', 'cv_link')}),
        ("Confidentialité choisie par le candidat",
         {'fields': ('show_photo', 'show_city', 'show_bio', 'show_experience', 'share_with_recruiters')}),
        ("Gestion Lantante", {'fields': ('is_published', 'admin_notes', 'created_at', 'updated_at')}),
    )

    @admin.display(description="Candidat")
    def name(self, obj):
        return obj.name

    @admin.display(description="CV")
    def cv_link(self, obj):
        if obj.pk and obj.cv:
            return format_html('<a href="{}" target="_blank">Ouvrir le CV</a>',
                               reverse('emploi:cv_download', args=[obj.pk]))
        return "—"

    @admin.display(description="Contact")
    def contact_info(self, obj):
        if not obj.pk:
            return "—"
        return format_html("{} · {}", obj.user.email, obj.phone or obj.user.phone or "pas de téléphone")


# ─────────────────────────────
# 🏢 Entreprises
# ─────────────────────────────
@admin.register(EmployerProfile)
class EmployerProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'sector', 'city', 'employees_count', 'is_verified', 'partner', 'created_at')
    list_filter = ('is_verified', 'sector')
    search_fields = ('company_name', 'user__email', 'city')
    autocomplete_fields = ('user', 'partner')
    readonly_fields = ('document_link',)
    actions = ['verify', 'unverify']

    @admin.display(description="Document de l'entreprise")
    def document_link(self, obj):
        if obj.pk and obj.document:
            return format_html('<a href="{}" target="_blank">Télécharger le document</a>',
                               reverse('emploi:employer_document', args=[obj.pk]))
        return "—"

    @admin.action(description="✓ Vérifier les entreprises sélectionnées")
    def verify(self, request, queryset):
        for emp in queryset.filter(is_verified=False):
            emp.is_verified = True
            emp.save(update_fields=['is_verified'])
            notify(emp.user, "Votre entreprise est vérifiée : vos offres sont publiées directement.", '/emploi/mon-espace/')
        self.message_user(request, "Entreprises vérifiées.")

    @admin.action(description="Retirer la vérification")
    def unverify(self, request, queryset):
        queryset.update(is_verified=False)


# ─────────────────────────────
# 💼 Offres et demandes
# ─────────────────────────────
@admin.register(JobOffer)
class JobOfferAdmin(SuggestionsMixin, admin.ModelAdmin):
    list_display = ('title', 'company_name', 'domain', 'contract', 'city', 'status', 'is_featured',
                    'deadline', 'suggestions_link')
    list_filter = ('status', 'domain', 'contract', 'is_featured')
    list_editable = ('status', 'is_featured')
    search_fields = ('title', 'description', 'employer__company_name', 'city')
    filter_horizontal = ('skills',)
    autocomplete_fields = ('employer',)
    actions = ['publish', 'close']

    @admin.action(description="✓ Publier les offres sélectionnées")
    def publish(self, request, queryset):
        for offer in queryset.exclude(status='published'):
            offer.status = 'published'
            offer.save(update_fields=['status'])
            if offer.employer_id:
                notify(offer.employer.user, f"Votre offre « {offer.title} » est publiée.", offer.get_absolute_url())

    @admin.action(description="Clôturer les offres sélectionnées")
    def close(self, request, queryset):
        queryset.update(status='closed')


@admin.register(StaffingRequest)
class StaffingRequestAdmin(SuggestionsMixin, admin.ModelAdmin):
    list_display = ('title', 'employer', 'domain', 'positions', 'city', 'urgency', 'status',
                    'created_at', 'suggestions_link')
    list_filter = ('status', 'urgency', 'domain')
    list_editable = ('status',)
    search_fields = ('title', 'employer__company_name', 'description')
    filter_horizontal = ('skills',)
    autocomplete_fields = ('employer',)


# ─────────────────────────────
# 🔗 Candidatures / correspondances / contrats
# ─────────────────────────────
class PlacementInline(admin.StackedInline):
    model = Placement
    extra = 0


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'offer', 'request', 'origin', 'status', 'created_at')
    list_filter = ('status', 'origin')
    list_editable = ('status',)
    search_fields = ('candidate__user__first_name', 'candidate__user__last_name', 'candidate__headline',
                     'offer__title', 'request__title')
    autocomplete_fields = ('candidate', 'offer', 'request')
    inlines = [PlacementInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and 'status' in form.changed_data:
            notify(obj.candidate.user,
                   f"Votre dossier « {obj.offer or obj.request} » est passé au statut : {obj.get_status_display()}",
                   '/emploi/mon-espace/')


@admin.register(Placement)
class PlacementAdmin(admin.ModelAdmin):
    list_display = ('application', 'contract', 'start_date', 'salary', 'fee', 'status')
    list_filter = ('status', 'contract')
    autocomplete_fields = ('application',)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'candidate', 'employer', 'scheduled_at', 'place', 'status')
    list_filter = ('status',)
    date_hierarchy = 'scheduled_at'
    autocomplete_fields = ('candidate', 'employer', 'application')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            notify(obj.candidate.user, f"Rendez-vous proposé : {obj.title} le {obj.scheduled_at:%d/%m/%Y à %H:%M}",
                   '/emploi/rendez-vous/')


# ─────────────────────────────
# 💬 Messagerie (supervision)
# ─────────────────────────────
class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ('sender', 'body', 'created_at')
    readonly_fields = ('sender', 'body', 'created_at')
    can_delete = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'participant_names', 'updated_at')
    inlines = [MessageInline]
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description="Participants")
    def participant_names(self, obj):
        return ", ".join(u.public_name for u in obj.participants.all())


# ─────────────────────────────
# 📰 Fil d'actualités (modération)
# ─────────────────────────────
class CommentInline(admin.TabularInline):
    model = FeedComment
    extra = 0
    fields = ('author', 'text', 'is_hidden')


@admin.register(FeedPost)
class FeedPostAdmin(admin.ModelAdmin):
    list_display = ('author_label', 'short_text', 'is_hidden', 'created_at')
    list_filter = ('is_hidden',)
    list_editable = ('is_hidden',)
    search_fields = ('text', 'author__email', 'author__first_name', 'author__last_name')
    inlines = [CommentInline]

    @admin.display(description="Texte")
    def short_text(self, obj):
        return obj.text[:80]


# ─────────────────────────────
# 🔔 Notifications
# ─────────────────────────────
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('text', 'recipient', 'is_read', 'created_at')
    list_filter = ('is_read',)

    def get_queryset(self, request):
        # Chacun voit d'abord ses propres notifications ; le super-admin voit tout.
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(recipient=request.user)
