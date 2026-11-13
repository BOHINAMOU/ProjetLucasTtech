"""API REST de l'application mobile Flutter : préfixe /api/mobile/v1/."""
from django.urls import path

from . import catalog, shop, views

app_name = 'api_mobile'

urlpatterns = [
    # Compte
    path('auth/login/', views.login, name='login'),
    path('auth/register/', views.register, name='register'),
    path('auth/verify-email/', views.verify_email, name='verify_email'),
    path('auth/resend-code/', views.resend_code, name='resend_code'),
    path('auth/logout/', views.logout, name='logout'),
    path('auth/password-reset/', views.password_reset, name='password_reset'),
    path('auth/password-reset/confirm/', views.password_reset_confirm, name='password_reset_confirm'),
    path('me/', views.me, name='me'),
    path('me/profil/', shop.profil, name='profil'),
    path('contact/', shop.contact, name='contact'),
    path('pages/<slug:slug>/', shop.page, name='page'),
    path('paiements/moyens/', shop.moyens, name='moyens'),
    path('paiements/', shop.payer, name='payer'),
    path('paiements/<str:reference>/', shop.paiement, name='paiement'),
    path('telechargements/', catalog.telechargements, name='telechargements'),
    path('abonnements/<int:pk>/concours/', shop.abonnement_concours, name='abonnement_concours'),

    # Accueil et catalogues
    path('home/', views.home, name='home'),
    path('carrousel/', catalog.carrousel, name='carrousel'),
    path('version/', catalog.version, name='version'),
    path('auth/web/', views.web_login, name='web_login'),
    path('evenements/', catalog.evenements, name='evenements'),
    path('evenements/<int:pk>/', catalog.evenement, name='evenement'),
    path('formations/', catalog.formations, name='formations'),
    path('formations/categories/', catalog.formation_categories, name='formation_categories'),
    path('formations/<int:pk>/', catalog.formation, name='formation'),
    path('boutique/produits/', catalog.produits, name='produits'),
    path('boutique/categories/', catalog.boutique_categories, name='boutique_categories'),
    path('boutique/produits/<int:pk>/', catalog.produit, name='produit'),
    path('services/espace/', catalog.espace_services, name='espace_services'),
    path('services/', catalog.services, name='services'),
    path('services/categories/', catalog.service_categories, name='service_categories'),
    path('services/<int:pk>/', catalog.service, name='service'),
    path('publications/', catalog.publications, name='publications'),
    path('publications/categories/', catalog.publication_categories, name='publication_categories'),
    path('publications/<int:pk>/', catalog.publication, name='publication'),
    path('partenaires/', catalog.partenaires, name='partenaires'),
    path('partenaires/<int:pk>/', catalog.partenaire, name='partenaire'),

    # Concours
    path('concours/categories/', views.concours_categories, name='concours_categories'),
    path('concours/annonces/', catalog.annonces, name='annonces'),
    path('concours/', views.concours_list, name='concours_list'),
    path('concours/<slug:slug>/annonces/', catalog.annonces, name='concours_annonces'),
    path('concours/<slug:slug>/', views.concours_detail, name='concours_detail'),
    path('concours/<slug:slug>/annees/<int:pk>/', views.concours_annee, name='concours_annee'),
    path('documents/<str:kind>/<int:pk>/', views.document, name='document'),
    path('documents/<str:kind>/<int:pk>/telecharger/', views.document_download, name='document_download'),

    # Abonnements et historique
    path('formules/', views.formules, name='formules'),
    path('abonnements/', views.abonnements, name='abonnements'),
    path('historique/', views.historique, name='historique'),
    path('historique/<str:cle>/', views.historique_detail, name='historique_detail'),
    path('achats/<str:reference>/telecharger/', views.telechargement, name='telechargement'),
]
