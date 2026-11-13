"""Prépare les images légères (WebP 400 / 800 / 1080 px) de toutes les images du site, pour que l'appli
n'attende jamais leur création à la première ouverture.  Usage : python manage.py miniatures"""
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.models import ImageField

from api_mobile.thumbs import thumb_url


class Command(BaseCommand):
    help = "Génère les miniatures WebP des images (400, 800 et 1080 px)."

    def handle(self, *args, **opts):
        n = 0
        for model in apps.get_models():
            champs = [f.name for f in model._meta.get_fields() if isinstance(f, ImageField)]
            if not champs:
                continue
            for obj in model.objects.all().only('pk', *champs).iterator():
                for c in champs:
                    f = getattr(obj, c)
                    if f:
                        for size in (400, 800, 1080):
                            if thumb_url(f, size):
                                n += 1
        self.stdout.write(f"{n} miniatures prêtes.")
