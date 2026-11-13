"""Page « Application mobile » : téléchargement direct de l'APK Android (servi depuis /media/app/)."""
import os

from django.conf import settings
from django.shortcuts import render

APK_PATH = 'app/Lantante.apk'


def current_apk():
    """(url, taille en Mo, version) de l'APK publié. Lien PROPRE À LA VERSION (Lantante-1.2.0.apk) :
    les navigateurs gardent /media/ en cache 7 jours, un lien fixe pourrait redonner une ancienne version."""
    import json
    url, version = settings.MEDIA_URL + APK_PATH, ''
    try:
        with open(os.path.join(settings.MEDIA_ROOT, 'app', 'version.json'), 'rb') as fh:
            data = json.loads(fh.read().decode('utf-8', 'replace'))
        version = str(data.get('version') or '')
        candidate = f'app/Lantante-{version}.apk'
        if version and os.path.exists(os.path.join(settings.MEDIA_ROOT, candidate)):
            url = settings.MEDIA_URL + candidate
    except (OSError, ValueError):
        pass
    path = os.path.join(settings.MEDIA_ROOT, url[len(settings.MEDIA_URL):])
    try:
        size_mb = round(os.path.getsize(path) / 1024 / 1024)
    except OSError:
        size_mb = None
    return url, size_mb, version


def application(request):
    url, size_mb, version = current_apk()
    resp = render(request, 'core/application.html', {'apk_url': url, 'apk_size': size_mb or 37, 'apk_version': version})
    resp['Cache-Control'] = 'no-cache'
    return resp


def telecharger(request):
    """Téléchargement de l'APK avec le BON type Android (application/vnd.android.package-archive) et un nom
    simple « Lantante.apk » : certains installateurs (Tecno, Infinix…) refusent un .apk reçu comme
    « application/octet-stream » ou au nom compliqué. Pas de cache : toujours la dernière version."""
    from django.http import FileResponse, Http404
    url, _size, version = current_apk()
    path = os.path.join(settings.MEDIA_ROOT, url[len(settings.MEDIA_URL):])
    if not os.path.exists(path):
        raise Http404
    resp = FileResponse(open(path, 'rb'), content_type='application/vnd.android.package-archive',
                        as_attachment=True, filename='Lantante.apk')
    resp['Cache-Control'] = 'no-store'
    resp['Content-Length'] = os.path.getsize(path)
    return resp
