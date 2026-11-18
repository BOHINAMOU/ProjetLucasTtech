from django.contrib import admin, messages
from django.db.models import Sum
from django.utils import timezone
from django.utils.html import format_html

from .models import ContactOffre, OffreEmploi


def _notifier(offre):
    """Notification « Nouvelle offre d'emploi » à tous (une seule fois)."""
    from api_mobile import push
    from api_mobile.models import Notification
    n = Notification.objects.create(titre="Nouvelle offre d'emploi", message=f"{offre.titre} — {offre.entreprise}",
                                    audience='tous')
    push.apres_creation(n)
    OffreEmploi.objects.filter(pk=offre.pk).update(notifie_le=timezone.now())


class ContactOffreInline(admin.TabularInline):
    model = ContactOffre
    extra = 1
    fields = ['libelle', 'telephone', 'whatsapp', 'ordre']


@admin.register(OffreEmploi)
class OffreEmploiAdmin(admin.ModelAdmin):
    inlines = [ContactOffreInline]
    list_display = ['titre', 'entreprise', 'ville', 'type_contrat', 'date_limite', 'statut', 'vues', 'clics', 'est_exemple']
    list_filter = ['publie', 'type_contrat', 'ville', 'est_exemple']
    search_fields = ['titre', 'entreprise', 'ville', 'description']
    actions = ['supprimer_exemples']
    fieldsets = (
        (None, {'fields': ('titre', 'image', 'entreprise', 'ville', 'type_contrat', 'description', 'date_limite')}),
        ("Contacts (au moins un)", {'fields': ('telephone', 'whatsapp', 'lien', 'email_contact'),
                                    'description': "Chaque bouton (Appeler, WhatsApp, Postuler, E-mail) n'apparaît que si son champ est rempli."}),
        ("Statistiques", {'fields': ('vues', 'clics_appel', 'clics_whatsapp', 'clics_lien', 'clics_email')}),
        ("Publication", {'fields': ('publie', 'notifier', 'est_exemple', 'created_at')}),
    )

    readonly_fields = ['vues', 'clics_appel', 'clics_whatsapp', 'clics_lien', 'clics_email']

    @admin.display(description="Clics (appel · WhatsApp · postuler)")
    def clics(self, o):
        return f"{o.clics_appel} · {o.clics_whatsapp} · {o.clics_lien}"

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
            t = OffreEmploi.objects.aggregate(v=Sum('vues'), a=Sum('clics_appel'), w=Sum('clics_whatsapp'), l=Sum('clics_lien'))
            self.message_user(request, f"{actives().count()} offre(s) en ligne · {t['v'] or 0} vues · "
                                       f"{t['a'] or 0} appels · {t['w'] or 0} WhatsApp · {t['l'] or 0} « Postuler ».", messages.INFO)
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
