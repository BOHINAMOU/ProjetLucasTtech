from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import path, include, re_path
from django.views.generic import RedirectView, TemplateView
from django.views.static import serve as serve_static

from Emploi.webapp import webapp

from .sitemaps import sitemaps

urlpatterns = [
    path(
        'ads.txt',
        lambda request: HttpResponse("google.com, pub-2908722543426563, DIRECT, f08c47fec0942fa0", content_type="text/plain"),
    ),
    path(
        'googlef89010971d315902.html',
        lambda request: HttpResponse("google-site-verification: googlef89010971d315902.html", content_type="text/html"),
    ),
    # Module Emploi retiré du site (nov. 2026) : ses anciennes adresses renvoient à l'accueil.
    re_path(r'^(?:emploi|app)(?:/.*)?$', RedirectView.as_view(url='/', permanent=False)),
    re_path(r'^app/(?P<path>.*)$', webapp, name='webapp'),
    path('users/',        include('Users.urls', namespace='users')),
    path('lantanteAdminTech/', admin.site.urls),
    path('shop/',         include('Shop.urls')),
    path('',              include('core.urls')),
    path('formations/',   include('Formations.urls', namespace='formations')),
    path('services/',     include('Services.urls', namespace='services')),
    path('actualites/', include('Publications.urls', namespace='publications')),
    # Ancienne adresse : redirection permanente (liens déjà partagés, référencement Google)
    re_path(r'^publications/(?P<rest>.*)$', RedirectView.as_view(url='/actualites/%(rest)s', permanent=True, query_string=True)),
    path('paiement/',     include('Payments.urls', namespace='payments')),
    path('evenements/',   include('Events.urls', namespace='events')),
    path('concours/',     include('concours.urls', namespace='concours')),
    path('abonnements/',  include('abonnements.urls', namespace='abonnements')),
    path('bohinamou/',    include('Portfolio.urls', namespace='portfolio')),
    path('emploi/',       include('Emploi.urls', namespace='emploi')),
    path('api/v1/',       include('Emploi.api.urls')),
    path('social-auth/',  include('social_django.urls', namespace='social')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
]

# Sert les fichiers médias (logos, photos produits, images d'équipe...)
# même hors DEBUG. Le helper django.conf.urls.static.static() ne fait
# volontairement rien quand DEBUG=False, donc on branche directement
# la vue de service — le projet n'a pas de stockage objet (S3/Cloudinary)
# ni de disque persistant Render, donc sans cette route chaque
# /media/... renvoie une 404 en production. Idéalement à remplacer par
# un vrai stockage objet + CDN quand le volume de trafic le justifiera.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve_static, {'document_root': settings.MEDIA_ROOT}),
]