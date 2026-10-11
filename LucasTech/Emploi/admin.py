from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    AccountBan, Appointment, Application, AvailabilitySlot, CandidateDocument, CandidateProfile, Conversation, EmployerProfile,
    FeedComment, FeedPost, JobOffer, Message, Notification, Placement,
    ModerationWarning, ProfileRevision, PublicationOrder, ServicePlan, Skill, StaffProfile, StaffingRequest,
)
from . import billing
from .services import (
    MAX_WARNINGS, active_warning_count, apply_warning, assign_conversation, ban_user, can_sanction, decide_employer,
    notify, notify_application_status, share_application, suggest_candidates, unban_user, warn_user,
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
                    'share_with_recruiters', 'is_published', 'moderation', 'updated_at')
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

    @admin.display(description="Modération")
    def moderation(self, obj):
        return moderation_cell(obj.user)

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
    list_display = ('company_name', 'sector', 'city', 'employees_count', 'status', 'is_verified', 'partner',
                    'moderation', 'created_at')
    list_filter = ('status', 'is_verified', 'publishing_free', 'sector')
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
                                             'publishing_free', 'partner', 'admin_notes')}),
    )

    @admin.display(description="Modération")
    def moderation(self, obj):
        return moderation_cell(obj.user)

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
    actions = ['publish', 'mark_filled', 'close']

    @admin.action(description="✓ Marquer comme pourvue (l'offre disparaît)")
    def mark_filled(self, request, queryset):
        count = queryset.exclude(status='filled').update(status='filled')
        self.message_user(request, f"{count} offre(s) marquée(s) pourvue(s) : elles ont disparu du site.")

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


class TreatmentFilter(admin.SimpleListFilter):
    """Onglets de gestion : par défaut seule la liste « En attente » est affichée."""
    title = "Traitement"
    parameter_name = 'traitement'

    def lookups(self, request, model_admin):
        return [
            ('pending', "En attente"),
            ('progress', "Présélectionnés / entretien"),
            ('hired', "Acceptés"),
            ('refused', "Rejetés"),
            ('treated', "Traités"),
            ('all', "Toutes"),
        ]

    def queryset(self, request, queryset):
        value = self.value() or 'pending'
        if value == 'pending':
            return queryset.filter(status='received')
        if value == 'progress':
            return queryset.filter(status__in=('shortlisted', 'interview'))
        if value in ('hired', 'refused', 'treated'):
            return queryset.filter(status=value)
        return queryset

    def choices(self, changelist):
        current = self.value() or 'pending'
        for lookup, title in self.lookup_choices:
            yield {
                'selected': current == lookup,
                'query_string': changelist.get_query_string({self.parameter_name: lookup}),
                'display': title,
            }


class CompletenessFilter(admin.SimpleListFilter):
    title = "Dossier"
    parameter_name = 'dossier'

    def lookups(self, request, model_admin):
        return [('incomplete', "Dossier incomplet"), ('complete', "Dossier complet")]

    def queryset(self, request, queryset):
        if self.value() not in ('incomplete', 'complete'):
            return queryset
        wanted = self.value() == 'incomplete'
        ids = [a.pk for a in queryset.select_related('candidate__user', 'offer') if a.is_incomplete == wanted]
        return queryset.filter(pk__in=ids)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'company', 'offer', 'request', 'completeness', 'status', 'shared_with_employer',
                    'share_link', 'treat_link', 'created_at')
    list_filter = (TreatmentFilter, CompletenessFilter, 'status', 'origin', 'shared_with_employer', 'offer__employer',
                   'offer__contract')
    list_editable = ('status',)
    readonly_fields = ('shared_at', 'share_link', 'interview_link', 'company', 'completeness')
    actions = ['mark_shortlisted', 'share_selected', 'mark_refused', 'mark_treated', 'request_missing']
    change_list_template = 'admin/emploi/application_change_list.html'

    @admin.display(description="Entreprise (origine de l'offre)")
    def company(self, obj):
        employer = obj.employer
        return employer.company_name if employer else "Lantante (offre directe)"

    @admin.display(description="Dossier")
    def completeness(self, obj):
        missing = obj.missing_items
        if not obj.pk:
            return "—"
        if missing:
            return format_html('<span class="badge badge-danger" title="{}">Dossier incomplet</span><br><small class="text-muted">{}</small>',
                               ", ".join(missing), "Manque : " + ", ".join(missing))
        return mark_safe('<span class="badge badge-success">Complet</span>')

    @admin.display(description="Traiter")
    def treat_link(self, obj):
        if not obj.pk or obj.status == 'treated':
            return "—"
        url = reverse('admin:emploi_application_treat', args=[obj.pk])
        return format_html('<a class="btn btn-xs btn-outline-secondary" href="{}"><i class="fas fa-check"></i> Traiter</a>', url)

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
            path('<int:pk>/traiter/', self.admin_site.admin_view(self.treat_view),
                 name='emploi_application_treat'),
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
        apps = list(Application.objects.select_related('offer__employer', 'request__employer', 'candidate__user'))
        counts = {code: 0 for code, _ in Application.STATUS}
        companies = {}
        incomplete = 0
        for app in apps:
            counts[app.status] += 1
            if app.status == 'received' and app.is_incomplete:
                incomplete += 1
            name = app.employer.company_name if app.employer else "Lantante (offres directes)"
            row = companies.setdefault(name, {'name': name, 'total': 0, 'pending': 0, 'progress': 0, 'treated': 0})
            row['total'] += 1
            if app.status == 'received':
                row['pending'] += 1
            elif app.status in ('shortlisted', 'interview'):
                row['progress'] += 1
            else:
                row['treated'] += 1
        extra_context = extra_context or {}
        extra_context['tab'] = request.GET.get('traitement') or 'pending'
        extra_context['stats'] = {
            'total': len(apps),
            'pending': counts['received'],
            'incomplete': incomplete,
            'progress': counts['shortlisted'] + counts['interview'],
            'hired': counts['hired'],
            'refused': counts['refused'],
            'treated': counts['treated'],
            'companies': sorted(companies.values(), key=lambda r: -r['total']),
        }
        return super().changelist_view(request, extra_context=extra_context)

    def treat_view(self, request, pk):
        application = get_object_or_404(Application.objects.select_related('candidate__user', 'offer', 'request'), pk=pk)
        if not self.has_change_permission(request, application):
            raise PermissionDenied
        back = reverse('admin:Emploi_application_changelist')
        if request.method == 'POST':
            application.status = 'treated'
            application.save(update_fields=['status', 'updated_at'])
            messages.success(request, f"Candidature de {application.candidate.name} marquée « Traité » : "
                                      "elle quitte la liste « En attente » et reste dans l'archive.")
            return redirect(back)
        return render(request, 'admin/emploi/treat.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': "Marquer la candidature comme traitée", 'application': application, 'back_url': back,
        })

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

    @admin.action(description="✓ Marquer comme traité (quitte la liste « En attente », reste dans l'archive)")
    def mark_treated(self, request, queryset):
        count = queryset.exclude(status='treated').update(status='treated')
        self.message_user(request, f"{count} candidature(s) marquée(s) « Traité » : elles quittent la liste « En attente ».")

    @admin.action(description="📎 Demander les éléments manquants au candidat")
    def request_missing(self, request, queryset):
        count = 0
        for app in queryset.select_related('candidate__user', 'offer', 'request'):
            missing = app.missing_items
            if not missing:
                continue
            target = app.offer or app.request
            notify(app.candidate.user,
                   f"Votre dossier pour « {target} » est incomplet. Merci de nous fournir : {', '.join(missing)}. "
                   "Vous pouvez compléter votre profil et vos documents depuis « Mon espace ».",
                   '/emploi/mon-espace/')
            count += 1
        self.message_user(request, f"{count} candidat(s) invité(s) à compléter leur dossier.")

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
    fields = ('author_name', 'author_role', 'body', 'created_at')
    readonly_fields = ('author_name', 'author_role', 'body', 'created_at')

    @admin.display(description="Auteur")
    def author_name(self, obj):
        return obj.author_name

    @admin.display(description="Rôle")
    def author_role(self, obj):
        return obj.author_role
    can_delete = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'kind', 'participant_names', 'assigned_to', 'status', 'updated_at')
    list_filter = ('kind', 'status', 'assigned_to')
    inlines = [MessageInline]
    readonly_fields = ('created_at', 'updated_at', 'reply_link', 'auto_reply_sent', 'intro_sent')
    fields = ('subject', 'kind', 'status', 'assigned_to', 'reply_link', 'auto_reply_sent', 'intro_sent',
              'created_at', 'updated_at')
    actions = ['take_charge', 'close_conversations']

    @admin.display(description="Participants")
    def participant_names(self, obj):
        return ", ".join(u.public_name for u in obj.participants.all())

    @admin.display(description="Répondre")
    def reply_link(self, obj):
        if obj.pk:
            return format_html('<a class="btn btn-sm btn-primary" href="{}" target="_blank">Ouvrir et répondre sur le site</a>',
                               reverse('emploi:conversation', args=[obj.pk]))
        return "—"

    def save_model(self, request, obj, form, change):
        # Attribuer / réattribuer à un collaborateur : le candidat est informé du changement d'interlocuteur.
        new = obj.assigned_to
        if change and 'assigned_to' in form.changed_data and new:
            obj.assigned_to_id = form.initial.get('assigned_to')
            super().save_model(request, obj, form, change)
            obj.refresh_from_db()
            assign_conversation(obj, new)
        else:
            super().save_model(request, obj, form, change)

    @admin.action(description="Me l'attribuer (prendre en charge)")
    def take_charge(self, request, queryset):
        for conv in queryset:
            assign_conversation(conv, request.user)
        self.message_user(request, "Conversations prises en charge. Vous vous présenterez avec votre première réponse.")

    @admin.action(description="Clôturer les conversations")
    def close_conversations(self, request, queryset):
        queryset.update(status='closed')


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'job_title')
    autocomplete_fields = ('user',)


# ─────────────────────────────
# 📰 Fil d'actualités (modération)
# ─────────────────────────────
class CommentInline(admin.TabularInline):
    model = FeedComment
    extra = 0
    fields = ('author', 'text', 'is_hidden')


@admin.register(FeedPost)
class FeedPostAdmin(admin.ModelAdmin):
    list_display = ('author_label', 'short_text', 'is_hidden', 'moderation', 'created_at')
    list_filter = ('is_hidden',)
    list_editable = ('is_hidden',)
    search_fields = ('text', 'author__email', 'author__first_name', 'author__last_name')
    inlines = [CommentInline]

    @admin.display(description="Texte")
    def short_text(self, obj):
        return obj.text[:80]

    @admin.display(description="Modération de l'auteur")
    def moderation(self, obj):
        return moderation_cell(obj.author)


# ─────────────────────────────
# 💳 Tarifs, commandes et paiements
# ─────────────────────────────
@admin.register(ServicePlan)
class ServicePlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'price', 'price_from', 'quote_only', 'duration_days', 'is_active', 'order')
    list_editable = ('price', 'price_from', 'quote_only', 'duration_days', 'is_active', 'order')
    list_filter = ('kind', 'is_active')
    prepopulated_fields = {'code': ('name',)}


STATUS_BADGES = {
    'quote': 'badge-info', 'awaiting_payment': 'badge-warning', 'payment_declared': 'badge-danger',
    'in_review': 'badge-primary', 'changes_requested': 'badge-warning', 'published': 'badge-success',
    'refused': 'badge-secondary', 'refunded': 'badge-secondary', 'cancelled': 'badge-light',
}


@admin.register(PublicationOrder)
class PublicationOrderAdmin(admin.ModelAdmin):
    list_display = ('reference', 'employer', 'plan', 'amount_label', 'status_badge', 'payment_reference', 'created_at')
    list_filter = ('status', 'plan__kind', 'payment_method')
    search_fields = ('employer__company_name', 'title', 'payment_reference', 'receipt_number')
    readonly_fields = ('reference', 'employer', 'plan', 'status', 'payer_phone', 'payment_method', 'payment_reference',
                       'paid_at', 'receipt_number', 'job_offer', 'staffing_request', 'feed_post', 'published_at',
                       'visible_until', 'created_at', 'updated_at', 'provider')
    fieldsets = (
        ("Commande", {'fields': ('reference', 'employer', 'plan', 'status', 'amount')}),
        ("Contenu", {'fields': ('title', 'post_kind', 'text', 'image', 'link_url', 'job_offer', 'staffing_request',
                                'feed_post')}),
        ("Paiement", {'fields': ('provider', 'payment_method', 'payer_phone', 'payment_reference', 'paid_at',
                                 'receipt_number')}),
        ("Décision de Lantante", {'fields': ('review_message', 'internal_note', 'published_at', 'visible_until',
                                             'created_at', 'updated_at'),
                                  'description': "Écrivez le message à l'entreprise (correction, refus, devis) AVANT de lancer l'action."}),
    )
    actions = ['confirm_payment', 'payment_not_received', 'approve', 'ask_changes', 'refuse', 'mark_refunded', 'send_quote']

    def has_add_permission(self, request):
        return False  # les commandes sont créées par les entreprises depuis le site

    @admin.display(description="Statut", ordering='status')
    def status_badge(self, obj):
        return format_html('<span class="badge {}">{}</span>', STATUS_BADGES.get(obj.status, 'badge-light'), obj.get_status_display())

    def _apply(self, request, queryset, allowed, func, done_text, need_message=False):
        done = skipped = 0
        for order in queryset.select_related('plan', 'employer__user'):
            if order.status not in allowed:
                skipped += 1
                continue
            if need_message and not order.review_message.strip():
                skipped += 1
                continue
            func(order)
            done += 1
        if done:
            self.message_user(request, f"{done} commande(s) : {done_text}.")
        if skipped:
            hint = " (écrivez d'abord le message à l'entreprise dans la fiche)" if need_message else ""
            self.message_user(request, f"{skipped} commande(s) ignorée(s), statut inadapté{hint}.", level=messages.WARNING)

    @admin.action(description="✓ Confirmer le paiement reçu (envoie le reçu, passe en validation)")
    def confirm_payment(self, request, queryset):
        self._apply(request, queryset, ('payment_declared', 'awaiting_payment'),
                    lambda o: billing.confirm_payment(o, request.user), "paiement confirmé, entreprise prévenue")

    @admin.action(description="✗ Paiement non retrouvé (demande de renvoyer la référence)")
    def payment_not_received(self, request, queryset):
        self._apply(request, queryset, ('payment_declared',),
                    lambda o: billing.payment_not_received(o, o.review_message), "entreprise invitée à vérifier son paiement")

    @admin.action(description="🌐 Valider et mettre en ligne")
    def approve(self, request, queryset):
        self._apply(request, queryset, ('in_review',), lambda o: billing.approve_order(o, request.user), "publiées")

    @admin.action(description="✏ Demander une correction (message à l'entreprise obligatoire)")
    def ask_changes(self, request, queryset):
        self._apply(request, queryset, ('in_review',), lambda o: billing.request_changes(o, o.review_message),
                    "correction demandée", need_message=True)

    @admin.action(description="⛔ Refuser (message obligatoire ; remboursement à faire si déjà payée)")
    def refuse(self, request, queryset):
        self._apply(request, queryset, ('in_review', 'changes_requested'), lambda o: billing.refuse_order(o, o.review_message),
                    "refusées", need_message=True)

    @admin.action(description="💸 Marquer comme remboursée")
    def mark_refunded(self, request, queryset):
        self._apply(request, queryset, ('refused',), lambda o: billing.mark_refunded(o, f"Remboursée par {request.user}"),
                    "marquées remboursées, entreprise prévenue")

    @admin.action(description="📄 Envoyer le devis (montant saisi dans la fiche)")
    def send_quote(self, request, queryset):
        done = 0
        for order in queryset.filter(status='quote', amount__gt=0):
            billing.send_quote(order, order.amount, order.review_message)
            done += 1
        self.message_user(request, f"{done} devis envoyé(s)." if done else
                          "Aucun devis envoyé : saisissez d'abord le montant dans la fiche (commande « En attente de devis »).",
                          level=messages.SUCCESS if done else messages.WARNING)


# ─────────────────────────────
# 🚫 Modération : avertissements et bannissements
# ─────────────────────────────
def moderation_cell(user):
    """Colonne « Modération » : compteur d'avertissements + boutons Avertir / Bannir."""
    if not can_sanction(user):
        return "—"
    ban = getattr(user, 'ban', None)
    if ban and ban.is_current:
        return mark_safe('<span class="badge badge-danger">Banni</span>')
    count = active_warning_count(user)
    warn_url = reverse('admin:emploi_sanction', args=['warn', user.pk])
    ban_url = reverse('admin:emploi_sanction', args=['ban', user.pk])
    return format_html(
        '<span class="badge {}">{}/{}</span> <a class="btn btn-xs btn-outline-warning" href="{}">Avertir</a> '
        '<a class="btn btn-xs btn-outline-danger" href="{}">Bannir</a>',
        'badge-warning' if count else 'badge-light', count, MAX_WARNINGS, warn_url, ban_url)


class SanctionViewsMixin:
    """Pages « Avertir » et « Bannir » (motif obligatoire, confirmation) accessibles depuis les listes."""

    def get_urls(self):
        return [
            path('sanction/<str:kind>/<int:user_id>/', self.admin_site.admin_view(self.sanction_view),
                 name='emploi_sanction'),
        ] + super().get_urls()

    def sanction_view(self, request, kind, user_id):
        from django.contrib.auth import get_user_model
        target = get_object_or_404(get_user_model(), pk=user_id)
        if kind not in ('warn', 'ban') or not request.user.is_staff or not can_sanction(target):
            raise PermissionDenied
        back = request.GET.get('next') or reverse('admin:Emploi_moderationwarning_changelist')
        if request.method == 'POST':
            reason = request.POST.get('reason', '').strip()
            if not reason:
                messages.error(request, "Le motif est obligatoire : il est expliqué à la personne.")
                return redirect(request.get_full_path())
            if kind == 'warn':
                warn_user(target, reason, by=request.user)
                count = active_warning_count(target)
                if count >= MAX_WARNINGS:
                    messages.warning(request, f"{target.public_name} a atteint {MAX_WARNINGS} avertissements : son compte est banni automatiquement.")
                else:
                    messages.success(request, f"Avertissement {count}/{MAX_WARNINGS} envoyé à {target.public_name}.")
            else:
                ban_user(target, reason, by=request.user)
                messages.success(request, f"{target.public_name} est banni : son compte est bloqué et ses contenus sont masqués.")
            return redirect(back)
        return render(request, 'admin/emploi/sanction.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta,
            'title': "Avertir" if kind == 'warn' else "Bannir", 'kind': kind, 'target': target,
            'count': active_warning_count(target), 'max': MAX_WARNINGS, 'back_url': back,
            'warnings': target.moderation_warnings.all()[:5],
        })


@admin.register(ModerationWarning)
class ModerationWarningAdmin(SanctionViewsMixin, admin.ModelAdmin):
    list_display = ('user', 'reason_short', 'issued_by', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'reason')
    autocomplete_fields = ('user',)
    readonly_fields = ('issued_by',)
    fields = ('user', 'reason', 'is_active', 'issued_by')

    @admin.display(description="Motif")
    def reason_short(self, obj):
        return obj.reason[:70]

    def save_model(self, request, obj, form, change):
        if not change:
            if not can_sanction(obj.user):
                messages.error(request, "Un membre de l'équipe ne peut pas recevoir d'avertissement.")
                return
            obj.issued_by = request.user
            super().save_model(request, obj, form, change)
            apply_warning(obj)  # prévient la personne ; bannit automatiquement au 3e avertissement
        else:
            super().save_model(request, obj, form, change)


@admin.register(AccountBan)
class AccountBanAdmin(admin.ModelAdmin):
    list_display = ('user', 'status_badge', 'automatic', 'banned_by', 'banned_at', 'lifted_at')
    list_filter = ('automatic',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'reason')
    autocomplete_fields = ('user',)
    readonly_fields = ('banned_by', 'lifted_at')
    actions = ['lift_ban']

    @admin.display(description="Statut")
    def status_badge(self, obj):
        if obj.is_current:
            return mark_safe('<span class="badge badge-danger">Banni</span>')
        return mark_safe('<span class="badge badge-success">Réactivé</span>')

    def save_model(self, request, obj, form, change):
        if not change:
            if not can_sanction(obj.user):
                messages.error(request, "Un membre de l'équipe ne peut pas être banni ici.")
                return
            ban_user(obj.user, obj.reason, by=request.user)  # crée/actualise le bannissement et bloque le compte
            return
        super().save_model(request, obj, form, change)

    @admin.action(description="✓ Lever le bannissement (réactive le compte, remet les avertissements à zéro)")
    def lift_ban(self, request, queryset):
        count = 0
        for ban in queryset.filter(lifted_at__isnull=True):
            unban_user(ban.user, by=request.user)
            count += 1
        self.message_user(request, f"{count} compte(s) réactivé(s). Leurs contenus restent masqués jusqu'à votre décision.")


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
