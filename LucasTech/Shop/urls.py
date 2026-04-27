from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    path('',                              views.shop,           name='shop'),
    path('produit/<int:pk>/',             views.product_detail, name='product_detail'),

    # Panier
    path('panier/',                       views.cart,           name='cart'),
    path('panier/ajouter/<int:pk>/',      views.add_to_cart,    name='add_to_cart'),
    path('panier/retirer/<int:item_id>/', views.cart_remove,    name='cart_remove'),

    # Commande → Paiement → Reçu
    path('commander/',                    views.checkout,       name='checkout'),
    path('paiement/<int:pk>/',            views.payment,        name='payment'),
    path('commande/<int:pk>/recu/',       views.order_receipt,  name='order_receipt'),
    path('historique/',                   views.order_history,  name='order_history'),

    # Réservation
    path('reserver/<int:pk>/',            views.reserve,        name='reserve'),
    path('reserver/merci/',               views.reserve_success, name='reserve_success'),

    # Avis
    path('avis/<int:pk>/',                views.add_review,     name='add_review'),
    path('paiement/succes/<int:pk>/', views.payment_success, name='payment_success'),
    # Shop/urls.py
# ...
    # ...
    path('historique-commandes/', views.order_history, name='order_history'),


]