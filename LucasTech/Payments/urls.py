from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('fedapay/webhook/', views.webhook, name='webhook'),
    path('<slug:kind>/<int:pk>/', views.checkout, name='checkout'),
    path('retour/<str:reference>/', views.callback, name='callback'),
    path('recu/<str:reference>/', views.result, name='result'),
    path('recu/<str:reference>/fichier/', views.download, name='download'),
    path('demo/<str:reference>/', views.demo, name='demo'),
]
