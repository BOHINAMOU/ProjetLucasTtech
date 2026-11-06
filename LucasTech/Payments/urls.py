from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('fedapay/webhook/', views.webhook, name='webhook'),
    path('<slug:kind>/<int:pk>/', views.checkout, name='checkout'),
    path('retour/<str:reference>/', views.callback, name='callback'),
    path('recu/<str:reference>/', views.result, name='result'),
    path('recu/<str:reference>/fichier/', views.download, name='download'),
    path('recu/<str:reference>/statut/', views.status, name='status'),
    path('recu/<str:reference>/pdf/', views.receipt, name='receipt'),
    path('demo/<str:reference>/', views.demo, name='demo'),
]
