from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import (
    Appointment, Application, AvailabilitySlot, CandidateDocument, CandidateProfile, Conversation, EmployerProfile,
    FeedComment, FeedPost, JobOffer, Message, Notification, Placement,
    ProfileRevision, Skill, StaffingRequest,
)
from .services import (
    decide_employer, notify, notify_application_status, share_application, suggest_candidates,
)


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


class CandidateDocumentInline(admin.TabularInline):
    model = CandidateDocument
    extra = 0
    fields = ('kind', 'title', 'open_link', 'created_at')
    readonly_fields = ('open_link', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Fichier")
    def open_link(self, obj):
        if obj.pk:
            return format_html('<a href="{}" target="_blank">Ouvrir</a>',
                               reverse('emploi:document_download', args=[obj.pk]))
        return "—"


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
    inlines = [CandidateDocumentInline, CandidateApplicationInline, ProfileRevisionInline]
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
    list_display = ('company_name', 'sector', 'city', 'employees_count', 'status', 'is_verified', 'partner', 'created_at')
    list_filter = ('status', 'is_verified', 'sector')
    list_editable = ('is_verified',)
    search_fields = ('company_name', 'user__email', 'city')
    autocomplete_fields = ('user', 'partner')
    readonly_fields = ('document_link', 'decided_at')
    actions = ['approve', 'reject', 'give_badge', 'remove_badge']
    fieldsets = (
        ("Entreprise", {'fields': ('user', 'company_name', 'logo', 'sector', 'city', 'employees_count',
                                   'description', 'products', 'website', 'whatsapp', 'contact_email')}),
        ("Document fourni", {'fields': ('document', 'document_link')}),
        ("Décision de Lantante", {'fields': ('status', 'decision_message', 'decided_at', 'is_verified',
                                             'partner', 'admin_notes')}),
    )

    @admin.display(description="Document de l'entreprise")
    def document_link(self, obj):
        if obj.pk and obj.document:
            return format_html('<a href="{}" target="_blank">Télécharger le document</a>',
                               reverse('emploi:employer_document', args=[obj.pk]))
        return "—"

    def save_model(self, request, obj, form, change):
        # Un changement de décision dans la fiche prévient automatiquement l'entreprise.
        new_status = obj.status
        if change and 'status' in form.changed_data:
            obj.status = form.initial.get('status', 'pending')
            super().save_model(request, obj, form, change)
            decide_employer(obj, new_status)
        else:
            super().save_model(request, obj, form, change)

    @admin.action(description="✓ Accepter les entreprises sélectionnées")
    def approve(self, request, queryset):
        for emp in queryset:
            decide_employer(emp, 'approved')
        self.message_user(request, "Entreprises acceptées et prévenues.")

    @admin.action(description="✗ Refuser les entreprises sélectionnées")
    def reject(self, request, queryset):
        for emp in queryset:
            decide_employer(emp, 'rejected')
        self.message_user(request, "Entreprises refusées et prévenues (ajoutez le motif dans « Message à l'entreprise »).")

    @admin.action(description="🔵 Donner le badge bleu")
    def give_badge(self, request, queryset):
        for emp in queryset:
            emp.is_verified = True
            emp.save(update_fields=['is_verified'])
            decide_employer(emp, 'approved')
            notify(emp.user, "Votre entreprise reçoit le badge bleu : vos offres sont publiées directement.", '/emploi/mon-espace/')

    @admin.action(description="Retirer le badge bleu")
    def remove_badge(self, request, queryset):
        queryset.update(is_verified=False)


# ─────────────────────────────
# 💼 Offres et demandes
# ─────────────────────────────
@admin.register(JobOffer)
class JobOfferAdmin(SuggestionsMixin, admin.ModelAdmin):
    list_display = ('title', 'company_name', 'domain', 'contract', 'city', 'status', 'applications_total',
                    'applications_pending', 'is_featured', 'deadline', 'suggestions_link')
    list_filter = ('status', 'domain', 'contract', 'is_featured')
    list_editable = ('status', 'is_featured')
    search_fields = ('title', 'description', 'employer__company_name', 'city')
    filter_horizontal = ('skills',)
    autocomplete_fields = ('employer',)
    actions = ['publish', 'close']

    def get_queryset(self, request):
        from django.db.models import Count, Q
        return super().get_queryset(request).annotate(
            _n_total=Count('applications', distinct=True),
            _n_pending=Count('applications', filter=Q(applications__status='received'), distinct=True))

    @admin.display(description="Candidatures", ordering='_n_total')
    def applications_total(self, obj):
        return obj._n_total

    @admin.display(description="En attente", ordering='_n_pending')
    def applications_pending(self, obj):
        return obj._n_pending

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
class AvailabilityInline(admin.TabularInline):
    model = AvailabilitySlot
    extra = 0
    fields = ('start', 'note')
    readonly_fields = ('start', 'note')
    can_delete = False
    verbose_name_plural = "Disponibilités proposées par le candidat pour l'entretien"

    def has_add_permission(self, request, obj=None):
        return False


class PlacementInline(admin.StackedInline):
    model = Placement
    extra = 0


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'company', 'offer', 'request', 'origin', 'status', 'shared_with_employer',
                    'share_link', 'created_at')
    list_filter = ('status', 'origin', 'shared_with_employer', 'offer__employer', 'offer__contract')
    list_editable = ('status',)
    readonly_fields = ('shared_at', 'share_link', 'interview_link', 'company')
    actions = ['share_selected', 'mark_shortlisted', 'mark_refused']
    change_list_template = 'admin/emploi/application_change_list.html'

    @admin.display(description="Entreprise (origine de l'offre)")
    def company(self, obj):
        employer = obj.employer
        return employer.company_name if employer else "Lantante (offre directe)"

    @admin.display(description="Entretien")
    def interview_link(self, obj):
        if not obj.pk:
            return "—"
        url = reverse('admin:emploi_application_interview', args=[obj.pk])
        return format_html('<a class="btn btn-sm btn-info" href="{}"><i class="fas fa-calendar-plus"></i> Fixer l\'entretien</a>', url)

    def get_urls(self):
        return [
            path('<int:pk>/transmettre/', self.admin_site.admin_view(self.share_view),
                 name='emploi_application_share'),
            path('<int:pk>/entretien/', self.admin_site.admin_view(self.interview_view),
                 name='emploi_application_interview'),
        ] + super().get_urls()

    @admin.display(description="Transmission à l'entreprise")
    def share_link(self, obj):
        if not obj.pk:
            return "—"
        if obj.shared_with_employer:
            return format_html('<span class="badge badge-success">Transmis le {}</span>',
                               obj.shared_at.strftime('%d/%m/%Y') if obj.shared_at else '')
        if not obj.employer:
            return "Pas d'entreprise liée"
        url = reverse('admin:emploi_application_share', args=[obj.pk])
        return format_html('<a class="btn btn-sm btn-success" href="{}"><i class="fas fa-paper-plane"></i> Transmettre à l\'entreprise</a>', url)

    def share_view(self, request, pk):
        application = get_object_or_404(Application, pk=pk)
        if not self.has_change_permission(request, application):
            raise PermissionDenied
        back = reverse('admin:Emploi_application_change', args=[pk])
        if request.method == 'POST':
            if share_application(application):
                messages.success(request, f"Dossier transmis à {application.employer.company_name} ; le candidat est prévenu.")
            else:
                messages.error(request, "Aucune entreprise liée à cette candidature : rien à transmettre.")
            return redirect(back)
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': "Transmettre le dossier à l'entreprise",
            'application': application,
            'back_url': back,
        }
        return render(request, 'admin/emploi/share_application.html', context)

    @admin.action(description="✉ Transmettre les dossiers sélectionnés à leur entreprise")
    def share_selected(self, request, queryset):
        done = sum(1 for app in queryset.select_related('offer__employer', 'request__employer', 'candidate__user')
                   if share_application(app))
        self.message_user(request, f"{done} dossier(s) transmis. Les candidats sans entreprise liée sont ignorés.")

    search_fields = ('candidate__user__first_name', 'candidate__user__last_name', 'candidate__headline',
                     'offer__title', 'request__title')
    autocomplete_fields = ('candidate', 'offer', 'request')
    inlines = [AvailabilityInline, PlacementInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Présélection, entretien, embauche, refus : le candidat est prévenu par e-mail avec le message saisi.
        if change and 'status' in form.changed_data:
            notify_application_status(obj)

    def changelist_view(self, request, extra_context=None):
        apps = list(Application.objects.select_related('offer__employer', 'request__employer'))
        total = len(apps)
        counts = {code: 0 for code, _ in Application.STATUS}
        companies = {}
        for app in apps:
            counts[app.status] += 1
            name = app.employer.company_name if app.employer else "Lantante (offres directes)"
            row = companies.setdefault(name, {'name': name, 'total': 0, 'pending': 0, 'treated': 0})
            row['total'] += 1
            row['pending' if app.status == 'received' else 'treated'] += 1
        extra_context = extra_context or {}
        extra_context['stats'] = {
            'total': total,
            'pending': counts['received'],
            'treated': total - counts['received'],
            'by_status': [(label, counts[code]) for code, label in Application.STATUS],
            'companies': sorted(companies.values(), key=lambda r: -r['total']),
        }
        return super().changelist_view(request, extra_context=extra_context)

    def interview_view(self, request, pk):
        application = get_object_or_404(Application.objects.select_related('candidate__user', 'offer', 'request'), pk=pk)
        if not self.has_change_permission(request, application):
            raise PermissionDenied
        back = reverse('admin:Emploi_application_change', args=[pk])
        target = application.offer or application.request
        if request.method == 'POST':
            from django.utils.dateparse import parse_datetime
            from django.utils import timezone
            when = parse_datetime(request.POST.get('when', ''))
            if not when:
                messages.error(request, "Choisissez la date et l'heure de l'entretien.")
                return redirect(request.path)
            if timezone.is_naive(when):
                when = timezone.make_aware(when)
            employer = application.employer
            Appointment.objects.create(
                application=application, candidate=application.candidate, employer=employer,
                title=f"Entretien — {target}", scheduled_at=when,
                place=request.POST.get('place', '')[:200], notes=request.POST.get('notes', ''))
            application.status = 'interview'
            application.save(update_fields=['status', 'updated_at'])
            local = timezone.localtime(when).strftime('%d/%m/%Y à %H:%M')
            place = f" Lieu / lien : {request.POST.get('place')}." if request.POST.get('place') else ""
            notify(application.candidate.user,
                   f"Votre entretien pour « {target} » est fixé le {local}.{place} Confirmez votre présence dans « Rendez-vous ».",
                   '/emploi/rendez-vous/')
            if employer and application.shared_with_employer:
                notify(employer.user, f"Entretien fixé avec {application.candidate.name} le {local} pour « {target} ».",
                       '/emploi/rendez-vous/')
            messages.success(request, f"Entretien fixé le {local} ; le candidat est prévenu.")
            return redirect(back)
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta, 'title': "Fixer l'entretien",
            'application': application, 'target': target, 'back_url': back,
            'slots': application.slots.all(),
        }
        return render(request, 'admin/emploi/interview.html', context)

    @admin.action(description="⭐ Présélectionner (e-mail + demande de disponibilités)")
    def mark_shortlisted(self, request, queryset):
        count = 0
        for app in queryset.exclude(status='shortlisted'):
            app.status = 'shortlisted'
            app.save(update_fields=['status', 'updated_at'])
            notify_application_status(app)
            count += 1
        self.message_user(request, f"{count} candidat(s) présélectionné(s) et prévenu(s) par e-mail.")

    @admin.action(description="✗ Refuser (e-mail avec le motif saisi dans « Message au candidat »)")
    def mark_refused(self, request, queryset):
        count = 0
        for app in queryset.exclude(status='refused'):
            app.status = 'refused'
            app.save(update_fields=['status', 'updated_at'])
            notify_application_status(app)
            count += 1
        self.message_user(request, f"{count} candidature(s) refusée(s) ; les candidats sont prévenus par e-mail.")


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
