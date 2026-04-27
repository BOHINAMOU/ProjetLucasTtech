from django.urls import path
from . import views

app_name = 'formations'

urlpatterns = [
    # Liste
    path('', views.formations, name='formations'),

    # Détail
    path('<int:pk>/', views.formation_detail, name='formation_detail'),

    # Panier
    path('panier/',                        views.cart,         name='cart'),
    path('panier/retirer/<int:item_id>/',  views.cart_remove,  name='cart_remove'),
    path('panier/commander/',              views.checkout,     name='checkout'),
]