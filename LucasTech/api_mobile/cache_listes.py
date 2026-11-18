"""Cache court (60 s) des listes publiques de l'appli, vidé dès qu'un contenu change dans l'admin.

Jamais de cache pour des données personnelles : `anonymes_seulement=True` pour les listes qui dépendent du compte
(accueil : droits sur les concours ; emplois : offres lues). Les épreuves payantes ne passent jamais par ici.
"""
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse

CLE_VERSION = 'listes:version'

# applications dont un changement rend les listes publiques obsolètes
APPS = {'Ecoles', 'Publications', 'Hotels', 'Logements', 'Offres', 'Shop', 'Events', 'Formations', 'Services',
        'concours', 'api_mobile', 'core', 'Marche', 'Repetiteurs'}
# modèles « personnels » ou trop fréquents : ils ne vident pas le cache
IGNORES = {'publicationlike', 'articlelu', 'offrelue', 'panierappli', 'notification', 'publicationcomment',
           'quickmessage', 'shoporder', 'shoporderitem'}


def version():
    v = cache.get(CLE_VERSION)
    if v is None:
        cache.add(CLE_VERSION, 1, None)
        v = cache.get(CLE_VERSION) or 1
    return v


def vider(**_):
    try:
        cache.incr(CLE_VERSION)
    except ValueError:
        cache.set(CLE_VERSION, 2, None)


def _changement(sender, **kw):
    m = sender._meta
    if m.app_label in APPS and m.model_name not in IGNORES:
        vider()


def brancher():
    from django.db.models.signals import post_delete, post_save
    post_save.connect(_changement, dispatch_uid='cache_listes_save', weak=False)
    post_delete.connect(_changement, dispatch_uid='cache_listes_delete', weak=False)


def _identifie(request):
    """Requête liée à un compte (jeton, session du site, test) : jamais servie depuis le cache commun."""
    from django.conf import settings
    return bool(request.META.get('HTTP_AUTHORIZATION') or request.COOKIES.get(settings.SESSION_COOKIE_NAME)
                or getattr(request, '_force_auth_user', None))


def cache_liste(secondes=60, anonymes_seulement=False):
    def deco(vue):
        @wraps(vue)
        def enveloppe(request, *a, **kw):
            if request.method != 'GET' or (anonymes_seulement and _identifie(request)):
                return vue(request, *a, **kw)
            cle = f"liste:{version()}:{request.get_host()}:{request.get_full_path()}"
            trouve = cache.get(cle)
            if trouve is not None:
                contenu, type_ = trouve
                r = HttpResponse(contenu, content_type=type_)
                r['X-Cache'] = 'HIT'
                return r
            r = vue(request, *a, **kw)
            if getattr(r, 'status_code', 500) == 200:
                if hasattr(r, 'render') and not getattr(r, 'is_rendered', True):
                    r.render()
                cache.set(cle, (r.content, r.get('Content-Type', 'application/json')), secondes)
            return r
        return enveloppe
    return deco
