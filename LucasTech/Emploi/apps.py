from django.apps import AppConfig


class EmploiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Emploi'
    verbose_name = "Emploi"

    def ready(self):
        from . import signals  # noqa: F401
