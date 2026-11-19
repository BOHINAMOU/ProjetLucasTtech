from django.apps import AppConfig


class ApiMobileConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api_mobile'
    verbose_name = "API de l'application mobile"

    def ready(self):
        from django.db.models.signals import post_save

        from .models import Notification

        def nouvelle(sender, instance, created, **kw):
            if created:
                from .push import apres_creation
                apres_creation(instance)

        post_save.connect(nouvelle, sender=Notification, dispatch_uid='push_notification', weak=False)

        from .cache_listes import brancher
        brancher()

        from .bande_admin import brancher as bande
        bande()
