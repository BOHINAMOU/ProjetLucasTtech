from django.urls import path

from . import views

app_name = 'abonnements'

urlpatterns = [
    path('', views.plans, name='plans'),
    path('mon-espace/', views.space, name='space'),
    path('souscrire/<slug:code>/', views.subscribe, name='subscribe'),
    path('mon-espace/<int:pk>/concours/', views.select, name='select'),
    path('mon-espace/<int:pk>/extension/', views.extend, name='extend'),
]
