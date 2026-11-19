from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from core import views as core_views
from django.urls import path, include, re_path
from core import a_traiter, admin_connexion, admin_evenements, admin_fiches, admin_hotels, admin_recherche
from django.views.generic import RedirectView, TemplateView
from django.views.static import serve as serve_static


from .sitemaps import sitemaps

urlpatterns = [
    path('repetiteurs/', include('Repetiteurs.urls')),
    path('vendre/', include('Marche.urls_vendre')),
    path('s/', include('Marche.urls_minisite')),
    path('emplois/', include('Offres.urls')),
    path('hotels/', include('Hotels.urls')),
    path('location/', include('Logements.urls')),
    path('restaurants/', include('Restaurants.urls')),
    re_path(r'^logements/(?P<rest>.*)$', RedirectView.as_view(url='/location/%(rest)s', permanent=True, query_string=True)),
    path('espace/', include('Marche.urls_espace')),
    path(
        'ads.txt',
        lambda request: HttpResponse("google.com, pub-2908722543426563, DIRECT, f08c47fec0942fa0", content_type="text/plain"),
    ),
    path(
        'googlef89010971d315902.html',
        lambda request: HttpResponse("google-site-verification: googlef89010971d315902.html", content_type="text/html"),
    ),
    # Ancien « Lantante Job » supprimé (nov. 2026) : ses adresses mènent aux Emplois, l'ancienne appli web à l'accueil.
    re_path(r'^emploi(?:/.*)?$', RedirectView.as_view(url='/emplois/', permanent=True)),
    re_path(r'^app(?:/.*)?$', RedirectView.as_view(url='/', permanent=True)),
    path('users/',        include('Users.urls', namespace='users')),
    path('lantanteAdminTech/verification/', admin_connexion.verification, name='admin_verification'),
    path('lantanteAdminTech/a-traiter/', a_traiter.page, name='admin_a_traiter'),
    path('lantanteAdminTech/recherche/', admin_recherche.recherche, name='admin_recherche'),
    path('lantanteAdminTech/section/evenements/<int:pk>/', admin_evenements.tableau, name='admin_evenement'),
    path('lantanteAdminTech/section/hotels/<int:pk>/', admin_hotels.fiche, name='admin_hotel'),
    path('lantanteAdminTech/section/vendeurs/<int:pk>/acces/', admin_fiches.vendeur_acces, name='admin_vendeur_acces'),
    path('lantanteAdminTech/section/services/<int:pk>/basculer/', admin_fiches.service_basculer, name='admin_service_basculer'),
    path('lantanteAdminTech/section/<str:code>/<int:pk>/', admin_fiches.fiche, name='admin_fiche'),
    path('lantanteAdminTech/section/evenements/<int:pk>/export/', admin_evenements.export_csv, name='admin_evenement_csv'),
    path('lantanteAdminTech/section/<slug:code>/', core_views.admin_section, name='admin_section'),
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
    path('api/mobile/v1/', include('api_mobile.urls', namespace='api_mobile')),
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