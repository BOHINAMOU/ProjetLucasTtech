"""Écran « Nous rejoindre » de l'appli : chaînes WhatsApp et réseaux sociaux de Lantante (réglages du site)."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api_mobile.catalog import public_cache

ORDRE = [('chaine_whatsapp_url', 'whatsapp', 'Chaîne WhatsApp Lantante Technologie'),
         ('chaine_info_url', 'whatsapp', 'Chaîne WhatsApp Lantante Technologie Info'),
         ('tiktok_url', 'tiktok', 'TikTok'), ('facebook_url', 'facebook', 'Facebook'),
         ('instagram_url', 'instagram', 'Instagram'), ('youtube_url', 'youtube', 'YouTube'),
         ('twitter_url', 'x', 'X'), ('telegram_url', 'telegram', 'Telegram')]


DOMAINES = {'whatsapp': ('whatsapp.com', 'wa.me'), 'tiktok': ('tiktok.com',), 'facebook': ('facebook.com', 'fb.com', 'fb.me'),
            'instagram': ('instagram.com',), 'youtube': ('youtube.com', 'youtu.be'), 'x': ('x.com', 'twitter.com'),
            'telegram': ('t.me', 'telegram.me', 'telegram.org')}


def _valide(code, url):
    """Un réseau n'est affiché que si son lien mène bien à ce réseau (pas de lien provisoire)."""
    from urllib.parse import urlparse
    hote = (urlparse((url or '').strip()).hostname or '').lower()
    return any(hote == d or hote.endswith('.' + d) for d in DOMAINES.get(code, ()))


@api_view(['GET'])
@permission_classes([AllowAny])
@public_cache(300)
def reseaux(request):
    from core.models import SiteSettings
    s = SiteSettings.load()
    return Response({'reseaux': [{'code': code, 'nom': nom, 'url': getattr(s, champ)}
                                 for champ, code, nom in ORDRE if _valide(code, getattr(s, champ, ''))]})
