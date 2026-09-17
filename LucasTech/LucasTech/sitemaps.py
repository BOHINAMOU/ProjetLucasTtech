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
        return ['core:home', 'core:projects', 'core:partners', 'core:team',
                'shop:shop', 'formations:formations', 'services:services',
                'publications:publications']

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return 1.0 if item == 'core:home' else 0.7


class ProductSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Product.objects.filter(is_available=True)

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
        return Publication.objects.filter(is_published=True)

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


sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'formations': FormationSitemap,
    'services': ServiceSitemap,
    'publications': PublicationSitemap,
    'projects': ProjectSitemap,
    'partners': PartnerSitemap,
    'team': TeamMemberSitemap,
}
