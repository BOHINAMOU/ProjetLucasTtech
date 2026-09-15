from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve as serve_static

urlpatterns = [
    path('users/',        include('Users.urls', namespace='users')),
    path('admin/',        admin.site.urls),
    path('shop/',         include('Shop.urls')),
    path('',              include('core.urls')),
    path('formations/',   include('Formations.urls', namespace='formations')),
    path('services/',     include('Services.urls', namespace='services')),
    path('publications/', include('Publications.urls', namespace='publications')),
    path('social-auth/',  include('social_django.urls', namespace='social')),
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