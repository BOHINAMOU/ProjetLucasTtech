from django.urls import path
from . import views

app_name = 'formations'

urlpatterns = [
    # Liste
    path('', views.formations, name='formations'),

    # Détail
    path('<int:pk>/', views.formation_detail, name='formation_detail'),

    # Inscription par formulaire
    path('<int:pk>/inscription/',         views.formation_register,         name='formation_register'),
    path('<int:pk>/inscription/merci/',   views.formation_register_success, name='formation_register_success'),

    # Téléchargement (formation numérique, après paiement)
    path('<int:pk>/telecharger/', views.formation_download, name='formation_download'),

    # Panier
    path('panier/',                        views.cart,         name='cart'),
    path('panier/retirer/<int:item_id>/',  views.cart_remove,  name='cart_remove'),
    path('panier/commander/',              views.checkout,     name='checkout'),
]