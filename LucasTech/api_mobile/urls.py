"""API REST de l'application mobile Flutter : préfixe /api/mobile/v1/."""
from django.urls import path

from . import views

app_name = 'api_mobile'

urlpatterns = [
    # Compte
    path('auth/login/', views.login, name='login'),
    path('auth/register/', views.register, name='register'),
    path('auth/logout/', views.logout, name='logout'),
    path('auth/password-reset/', views.password_reset, name='password_reset'),
    path('auth/password-reset/confirm/', views.password_reset_confirm, name='password_reset_confirm'),
    path('me/', views.me, name='me'),

    # Accueil et catalogues
    path('home/', views.home, name='home'),
    path('evenements/', views.evenements, name='evenements'),
    path('formations/', views.formations, name='formations'),
    path('boutique/produits/', views.produits, name='produits'),

    # Concours
    path('concours/categories/', views.concours_categories, name='concours_categories'),
    path('concours/', views.concours_list, name='concours_list'),
    path('concours/<slug:slug>/', views.concours_detail, name='concours_detail'),
    path('concours/<slug:slug>/annees/<int:pk>/', views.concours_annee, name='concours_annee'),
    path('documents/<str:kind>/<int:pk>/', views.document, name='document'),

    # Abonnements et historique
    path('formules/', views.formules, name='formules'),
    path('abonnements/', views.abonnements, name='abonnements'),
    path('historique/', views.historique, name='historique'),
    path('achats/<str:reference>/telecharger/', views.telechargement, name='telechargement'),
]
