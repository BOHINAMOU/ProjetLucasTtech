"""Page « Application mobile » : téléchargement direct de l'APK Android (servi depuis /media/app/)."""
import os

from django.conf import settings
from django.shortcuts import render

APK_PATH = 'app/Lantante.apk'


def application(request):
    size_mb = None
    try:
        size_mb = round(os.path.getsize(os.path.join(settings.MEDIA_ROOT, APK_PATH)) / 1024 / 1024)
    except OSError:
        pass
    return render(request, 'core/application.html', {
        'apk_url': settings.MEDIA_URL + APK_PATH, 'apk_size': size_mb or 52,
    })
