import time
from django.conf import settings
from .models import Partner, SiteSettings

def partners(request):
    return {
        'partners': Partner.objects.all()
    }


def site_settings(request):
    return {
        'site_settings': SiteSettings.load()
    }


def partner_cta(request):
    """Le bouton « Devenir partenaire » disparaît pour un partenaire, une entreprise ou une demande déjà déposée."""
    user = getattr(request, 'user', None)
    hide = False
    if user is not None and user.is_authenticated:
        from .models import PartnerApplication
        hide = (
            getattr(user, 'account_type', '') == 'employer'
            or hasattr(user, 'employer_profile')
            or PartnerApplication.objects.filter(email__iexact=user.email).exists()
        )
    return {'hide_partner_cta': hide}


def cache_bust(request):
    """
    En dev (DEBUG=True), force le navigateur à toujours recharger les
    fichiers statiques modifiés (le serveur local ne renvoie pas d'en-têtes
    de cache explicites, donc certains navigateurs les gardent en cache
    trop longtemps). Sans effet en production : les fichiers y sont déjà
    servis avec un nom haché par collectstatic (ManifestStaticFilesStorage),
    qui change automatiquement à chaque modification.
    """
    return {
        'cache_bust': int(time.time()) if settings.DEBUG else ''
    }