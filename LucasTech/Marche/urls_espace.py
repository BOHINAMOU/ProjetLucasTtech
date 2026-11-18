from django.urls import path

from . import espace as e

app_name = 'espace'

urlpatterns = [
    path('<str:code>/', e.connexion, name='connexion'),
    path('<str:code>/activer/<str:jeton>/', e.activer, name='activer'),
    path('<str:code>/oubli/', e.oubli, name='oubli'),
    path('<str:code>/deconnexion/', e.deconnexion, name='deconnexion'),
    path('<str:code>/tableau/', e.tableau, name='tableau'),
    path('<str:code>/produits/', e.produits, name='produits'),
    path('<str:code>/produits/ajouter/', e.produit, name='produit_ajouter'),
    path('<str:code>/produits/<int:pk>/', e.produit, name='produit'),
    path('<str:code>/produits/<int:pk>/supprimer/', e.produit_supprimer, name='produit_supprimer'),
    path('<str:code>/categories/', e.categories, name='categories'),
    path('<str:code>/commandes/', e.commandes, name='commandes'),
    path('<str:code>/parametres/', e.parametres, name='parametres'),
    path('<str:code>/mon-lien/', e.mon_lien, name='mon_lien'),
]
