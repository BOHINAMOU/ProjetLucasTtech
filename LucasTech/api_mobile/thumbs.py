"""Vignettes d'images (≈ 400 px, JPEG/WebP léger) pour l'application : générées une seule fois, à la première
demande, puis servies depuis MEDIA_ROOT/thumbs/. L'image pleine taille reste disponible à côté."""
import hashlib
import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)
THUMB_DIR = 'thumbs'


def thumb_name(field, size):
    try:
        name = field.name
    except AttributeError:
        return None
    if not name:
        return None
    digest = hashlib.sha1(f'{name}:{size}'.encode()).hexdigest()[:20]
    return f'{THUMB_DIR}/{size}/{digest}.webp'


class _Fichier:
    """Fichier de MEDIA_ROOT désigné par son chemin (images insérées dans le texte d'un article)."""
    def __init__(self, name):
        self.name = name
        self.path = os.path.join(settings.MEDIA_ROOT, name)


def media_file_from_url(url):
    """/media/xxx.jpg ou https://site/media/xxx.jpg -> objet fichier, si l'image est chez nous."""
    from urllib.parse import unquote, urlparse
    path = unquote(urlparse(url or '').path)
    if not path.startswith(settings.MEDIA_URL) or '..' in path:
        return None
    name = path[len(settings.MEDIA_URL):]
    return _Fichier(name) if name and os.path.isfile(os.path.join(settings.MEDIA_ROOT, name)) else None


def thumb_url(field, size=400):
    """Chemin public (/media/thumbs/...) de la vignette ; None si pas d'image ou en cas d'échec."""
    rel = thumb_name(field, size)
    if not rel:
        return None
    dest = os.path.join(settings.MEDIA_ROOT, rel)
    if not os.path.exists(dest):
        try:
            from PIL import Image, ImageOps
            src = field.path
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im)
                im.thumbnail((size, size), Image.LANCZOS)
                if im.mode not in ('RGB', 'RGBA'):
                    im = im.convert('RGBA' if 'A' in im.getbands() else 'RGB')
                tmp = dest + '.tmp'
                im.save(tmp, 'WEBP', quality=78, method=4)
                os.replace(tmp, dest)
        except Exception:  # fichier absent, format non pris en charge… : l'appli utilisera l'image pleine
            logger.warning("Vignette impossible pour %s", getattr(field, 'name', field), exc_info=True)
            return None
    return settings.MEDIA_URL + rel
