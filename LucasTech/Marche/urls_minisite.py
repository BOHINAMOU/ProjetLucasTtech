from django.urls import path

from . import minisite as m

app_name = 'minisite'

urlpatterns = [
    path('<slug:slug>/', m.accueil, name='accueil'),
    path('<slug:slug>/produits/', m.produits, name='produits'),
    path('<slug:slug>/produits/<int:pk>/', m.produit, name='produit'),
    path('<slug:slug>/contact/', m.contact, name='contact'),
]
