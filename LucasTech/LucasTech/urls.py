from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static

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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)