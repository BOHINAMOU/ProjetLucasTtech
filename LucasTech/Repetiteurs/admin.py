from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Repetiteur


@admin.register(Repetiteur)
class RepetiteurAdmin(admin.ModelAdmin):
    class Media:
        css = {'all': ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',)}
        js = ('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', 'admin/carte_produit.js')

    list_display = ['apercu', 'nom', 'matieres', 'ville', 'quartier', 'est_exemple', 'actif', 'ordre']
    list_display_links = ['apercu', 'nom']
    list_editable = ['actif', 'ordre']
    list_filter = ['actif', 'est_exemple', 'ville']
    actions = ['supprimer_exemples']
    search_fields = ['nom', 'matieres', 'ville', 'quartier', 'niveaux']
    fieldsets = (
        (None, {'fields': ('photo', 'photo_apercu', 'nom', 'matieres', 'niveaux', 'experience', 'tarif', 'description')}),
        ('Lieu', {'fields': ('ville', 'quartier', 'latitude', 'longitude'),
                  'description': "Facultatif : choisissez le lieu sur la carte (recherche, clic ou « Ma position »)."}),
        ('Contact', {'fields': ('whatsapp', 'email', 'telephone')}),
        ('Publication', {'fields': ('actif', 'est_exemple', 'ordre')}),
    )

    readonly_fields = ['photo_apercu']

    def changelist_view(self, request, extra_context=None):
        # « Supprimer tous les exemples » marche sans rien cocher.
        if request.method == 'POST' and request.POST.get('action') == 'supprimer_exemples'                 and not request.POST.getlist(admin.helpers.ACTION_CHECKBOX_NAME):
            post = request.POST.copy()
            post.setlist(admin.helpers.ACTION_CHECKBOX_NAME, [str(p) for p in Repetiteur.objects.values_list('pk', flat=True)[:1]])
            request.POST = post
        return super().changelist_view(request, extra_context)

    @admin.action(description="Supprimer tous les exemples")
    def supprimer_exemples(self, request, queryset):
        n, _ = Repetiteur.objects.filter(est_exemple=True).delete()
        self.message_user(request, f"{n} exemple(s) supprimé(s).", messages.SUCCESS)

    @admin.display(description="Aperçu")
    def photo_apercu(self, r):
        if not r.photo:
            return '—'
        return format_html('<img src="{}" style="width:120px;height:120px;object-fit:cover;border-radius:16px">', r.photo.url)

    @admin.display(description="")
    def apercu(self, r):
        if not r.photo:
            return '—'
        return format_html('<img src="{}" style="width:42px;height:42px;object-fit:cover;border-radius:10px">', r.photo.url)
