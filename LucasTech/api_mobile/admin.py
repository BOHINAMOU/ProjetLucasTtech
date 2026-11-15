from django.contrib import admin


from .models import CarouselItem, Notification


@admin.register(CarouselItem)
class CarouselItemAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'cible', 'cible_id', 'ordre', 'actif', 'debut', 'fin']
    list_editable = ['ordre', 'actif']
    list_filter = ['actif', 'cible']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['titre', 'audience', 'destinataire', 'lectures_n', 'automatique', 'created_at']
    list_filter = ['audience', 'automatique', 'created_at']
    search_fields = ['titre', 'message', 'utilisateur__email']
    autocomplete_fields = ['utilisateur']
    fields = ['titre', 'message', 'audience', 'groupe', 'utilisateur', 'cible', 'cible_id', 'lien']

    @admin.display(description="Pour")
    def destinataire(self, n):
        return n.utilisateur or n.groupe or 'Tous'

    @admin.display(description="Lue par")
    def lectures_n(self, n):
        return n.lectures.count()



from .models import Appareil  # noqa: E402


@admin.register(Appareil)
class AppareilAdmin(admin.ModelAdmin):
    list_display = ['user', 'plateforme', 'updated_at']
    search_fields = ['user__email']
    readonly_fields = ['user', 'jeton', 'plateforme', 'updated_at']

    def has_add_permission(self, request):
        return False
