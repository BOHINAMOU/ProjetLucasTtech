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

def offres_menu(request):
    """Menu « Offres » et pastilles « Autres services » : (code de l'appli, lien, nom)."""
    from django.urls import reverse
    return {'offres_menu': [
        ('services', reverse('services:services'), "Services numériques"),
        ('formations', reverse('formations:formations'), "Formations"),
        ('restaurants', reverse('restaurants:liste'), "Restaurants"),
        ('hotels', reverse('hotels:liste'), "Hôtels"),
        ('logements', reverse('logements:liste'), "Location"),
        ('repetiteurs', reverse('repetiteurs:liste'), "Répétiteurs"),
        ('ecoles', reverse('ecoles:liste'), "Écoles"),
        ('offres', reverse('offres:liste'), "Emplois"),
        ('events', reverse('events:list'), "Événements"),
        ('boutiques', reverse('boutiques'), "Boutiques des vendeurs"),
        ('contact', reverse('core:contact'), "Nous contacter"),
    ]}



def services_rapides(request):
    """Pastilles de l'accueil : services demandés le plus souvent (lien WhatsApp avec message prêt)."""
    if request.resolver_match is None or request.resolver_match.view_name != 'core:home':
        return {}
    return {'services_rapides': [
        ('fa-file-lines', 'Rédaction de CV'), ('fa-flag', 'CV canadien'), ('fa-bullhorn', "Publication d'annonces"),
        ('fa-address-card', 'Cartes de visite'), ('fa-book-open', 'Press-book'), ('fa-palette', "Création d'affiches"),
        ('fa-video', 'Vidéos publicitaires'), ('fa-laptop', 'Installation de système'), ('fa-ellipsis', 'Autres services'),
    ]}
