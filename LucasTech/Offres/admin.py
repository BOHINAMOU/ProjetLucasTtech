from django.conf import settings
from django.contrib import admin, messages
from django.core.mail import EmailMessage
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import CandidatureEmploi, OffreEmploi


def _notifier(offre):
    """Notification « Nouvelle offre d'emploi » à tous (une seule fois)."""
    from api_mobile import push
    from api_mobile.models import Notification
    n = Notification.objects.create(titre="Nouvelle offre d'emploi", message=f"{offre.titre} — {offre.entreprise}",
                                    audience='tous')
    push.apres_creation(n)
    OffreEmploi.objects.filter(pk=offre.pk).update(notifie_le=timezone.now())


class _CandidatureInline(admin.TabularInline):
    model = CandidatureEmploi
    extra = 0
    fields = ['nom', 'telephone', 'email', 'statut', 'cv_lien', 'created_at']
    readonly_fields = ['nom', 'telephone', 'email', 'cv_lien', 'created_at']
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="CV")
    def cv_lien(self, c):
        return format_html('<a href="{}" target="_blank" rel="noopener">Voir</a>', reverse('offres:cv', args=[c.pk])) if c.cv else '—'


@admin.register(OffreEmploi)
class OffreEmploiAdmin(admin.ModelAdmin):
    list_display = ['titre', 'entreprise', 'ville', 'type_contrat', 'date_limite', 'statut', 'vues', 'nb_candidatures', 'est_exemple']
    list_filter = ['publie', 'type_contrat', 'ville', 'est_exemple']
    search_fields = ['titre', 'entreprise', 'ville', 'description']
    actions = ['supprimer_exemples']
    inlines = [_CandidatureInline]
    fieldsets = (
        (None, {'fields': ('titre', 'image', 'entreprise', 'ville', 'type_contrat', 'description', 'date_limite')}),
        ("Pour postuler", {'fields': ('candidature_appli', 'telephone', 'whatsapp', 'email_contact', 'lien',
                                      'email_recruteur'),
                           'description': "Chaque bouton n'apparaît que si son champ est rempli."}),
        ("Publication", {'fields': ('publie', 'notifier', 'est_exemple', 'created_at')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_nb=Count('candidatures'))

    @admin.display(description="Candidatures", ordering='_nb')
    def nb_candidatures(self, o):
        return o._nb

    @admin.display(description="Statut")
    def statut(self, o):
        return format_html('<span style="color:{}">{}</span>', '#0b6137' if o.active else '#c62828',
                           "En ligne" if o.active else ("Expirée" if o.publie else "Masquée"))

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.notifier and obj.publie and not obj.notifie_le:
            _notifier(obj)
            self.message_user(request, "Notification envoyée.", messages.SUCCESS)

    def changelist_view(self, request, extra_context=None):
        from .api import actives
        if request.method == 'GET' and not request.GET:
            self.message_user(request, f"{actives().count()} offre(s) en ligne · "
                                       f"{CandidatureEmploi.objects.count()} candidature(s) reçue(s).", messages.INFO)
        if request.method == 'POST' and request.POST.get('action') == 'supprimer_exemples' \
                and not request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME):
            post = request.POST.copy()
            post.setlist(admin.helpers.ACTION_CHECKBOX_NAME, [str(p) for p in OffreEmploi.objects.values_list('pk', flat=True)[:1]])
            request.POST = post
        return super().changelist_view(request, extra_context)

    @admin.action(description="Supprimer tous les exemples")
    def supprimer_exemples(self, request, queryset):
        n, _ = OffreEmploi.objects.filter(est_exemple=True).delete()
        self.message_user(request, f"{n} élément(s) d'exemple supprimé(s).", messages.SUCCESS)


@admin.register(CandidatureEmploi)
class CandidatureEmploiAdmin(admin.ModelAdmin):
    list_display = ['nom', 'offre', 'telephone', 'statut', 'envoyee_recruteur', 'created_at']
    list_filter = ['statut', 'offre']
    list_editable = ['statut']
    search_fields = ['nom', 'telephone', 'email', 'offre__titre']
    readonly_fields = ['offre', 'user', 'nom', 'telephone', 'email', 'message', 'cv_lien', 'envoyee_recruteur', 'created_at']
    fields = ['offre', 'statut', 'nom', 'telephone', 'email', 'message', 'cv_lien', 'envoyee_recruteur', 'created_at']
    actions = ['envoyer_au_recruteur']

    def has_add_permission(self, request):
        return False

    @admin.display(description="CV")
    def cv_lien(self, c):
        return format_html('<a class="button" href="{}" target="_blank" rel="noopener">Télécharger le CV</a>',
                           reverse('offres:cv', args=[c.pk])) if c.cv else '—'

    def change_view(self, request, object_id, form_url='', extra_context=None):
        CandidatureEmploi.objects.filter(pk=object_id, statut='recue').update(statut='vue')
        return super().change_view(request, object_id, form_url, extra_context)

    @admin.action(description="Envoyer au recruteur par e-mail (avec le CV)")
    def envoyer_au_recruteur(self, request, queryset):
        n = 0
        for c in queryset.select_related('offre'):
            if not c.offre.email_recruteur:
                continue
            m = EmailMessage(f"Candidature : {c.offre.titre}",
                             f"Nom : {c.nom}\nTéléphone : {c.telephone}\nE-mail : {c.email}\n\n{c.message}\n\n— Lantante",
                             settings.DEFAULT_FROM_EMAIL, [c.offre.email_recruteur], reply_to=[c.email] if c.email else None)
            if c.cv:
                c.cv.open('rb')
                m.attach(c.cv.name.rsplit('/', 1)[-1], c.cv.read())
                c.cv.close()
            try:
                m.send(fail_silently=False)
            except Exception:
                continue
            c.envoyee_recruteur = True
            c.save(update_fields=['envoyee_recruteur'])
            n += 1
        self.message_user(request, f"{n} candidature(s) envoyée(s). Sans e-mail recruteur : ignorées.", messages.SUCCESS)
