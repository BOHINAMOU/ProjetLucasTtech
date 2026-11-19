from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from Shop.models import Product
from Formations.models import Formation
from Services.models import Service
from Publications.models import Publication
from core.models import Project, Partner, TeamMember


class StaticViewSitemap(Sitemap):
    changefreq = 'weekly'

    def items(self):
        return ['core:home', 'core:projects', 'core:team', 'core:partners', 'core:monetization',
                'shop:shop', 'formations:formations', 'services:services',
                'publications:publications', 'events:list', 'portfolio:home',
                'restaurants:liste', 'hotels:liste', 'logements:liste', 'repetiteurs:liste', 'ecoles:liste',
                'offres:liste', 'boutiques', 'concours:index', 'core:application', 'core:privacy_policy',
                'core:terms_of_service']

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return 1.0 if item == 'core:home' else 0.7


class ProductSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Product.en_vente()

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('shop:product_detail', args=[obj.pk])


class FormationSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Formation.objects.filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('formations:formation_detail', args=[obj.pk])


class ServiceSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return Service.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('services:service_detail', args=[obj.pk])


class PublicationSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return Publication.objects.filter(is_published=True, show_on_site=True)

    def location(self, obj):
        return reverse('publications:publication_detail', args=[obj.slug])


class ProjectSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return Project.objects.all()

    def lastmod(self, obj):
        return obj.created_at

    def location(self, obj):
        return reverse('core:project_detail', args=[obj.pk])


class PartnerSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.4

    def items(self):
        return Partner.objects.filter(is_active=True)

    def location(self, obj):
        return reverse('core:partner_detail', args=[obj.pk])


class TeamMemberSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.4

    def items(self):
        return TeamMember.objects.all()

    def location(self, obj):
        return reverse('core:team_member_detail', args=[obj.pk])


class PortfolioProjectSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.4

    def items(self):
        from Portfolio.models import Project as PortfolioProject
        return PortfolioProject.objects.filter(is_published=True)

    def location(self, obj):
        return reverse('portfolio:project_detail', args=[obj.slug])


class _Liste(Sitemap):
    """Fiches publiques d'une rubrique (même filtre que la page du site)."""
    changefreq = 'weekly'
    priority = 0.6

    def location(self, obj):
        return obj.get_absolute_url()


class RestaurantSitemap(_Liste):
    def items(self):
        from Restaurants.api import visibles
        return visibles()


class HotelSitemap(_Liste):
    def items(self):
        from Hotels.models import Hotel
        return Hotel.objects.filter(actif=True)


class RepetiteurSitemap(_Liste):
    def items(self):
        from api_mobile.repetiteurs import _actifs
        return _actifs()

    def location(self, obj):
        return reverse('repetiteurs:fiche', args=[obj.pk])


class EcoleSitemap(_Liste):
    def items(self):
        from Ecoles.models import Ecole
        return Ecole.objects.filter(publie=True)

    def location(self, obj):
        return reverse('ecoles:fiche', args=[obj.slug])


class OffreSitemap(_Liste):
    def items(self):
        from Offres.api import actives
        return actives()

    def location(self, obj):
        return reverse('offres:detail', args=[obj.pk])


class EventSitemap(_Liste):
    def items(self):
        from Events.models import Event
        return Event.objects.filter(is_published=True)


class BoutiqueSitemap(_Liste):
    def items(self):
        from Marche.models import Vendeur
        return [v for v in Vendeur.objects.filter(statut='valide').exclude(slug='').order_by('boutique') if v.actif]

    def location(self, obj):
        return reverse('minisite:accueil', args=[obj.slug])


sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'formations': FormationSitemap,
    'services': ServiceSitemap,
    'publications': PublicationSitemap,
    'projects': ProjectSitemap,
    'partners': PartnerSitemap,
    'team': TeamMemberSitemap,
    'portfolio_projects': PortfolioProjectSitemap,
    'restaurants': RestaurantSitemap,
    'hotels': HotelSitemap,
    'repetiteurs': RepetiteurSitemap,
    'ecoles': EcoleSitemap,
    'emplois': OffreSitemap,
    'evenements': EventSitemap,
    'boutiques': BoutiqueSitemap,
}
