"""Sert la version web de l'application « Lantante Technologie Job » (dossier webapp/, générée par `expo export --platform web`)."""
from django.conf import settings
from django.http import Http404
from django.views.decorators.http import require_GET
from django.views.static import serve

WEBAPP_ROOT = settings.BASE_DIR / 'webapp'


@require_GET
def webapp(request, path=''):
    """Un fichier existant (script, image, police) est servi tel quel ; toute autre adresse renvoie la page de l'application,
    qui affiche elle-même le bon écran (application à page unique)."""
    try:
        response = serve(request, path, document_root=WEBAPP_ROOT)
        if path.startswith('_expo/') or path.startswith('assets/'):
            response['Cache-Control'] = 'public, max-age=31536000, immutable'  # noms de fichiers à empreinte
        return response
    except Http404:
        response = serve(request, 'index.html', document_root=WEBAPP_ROOT)
        response['Cache-Control'] = 'no-cache'
        return response
