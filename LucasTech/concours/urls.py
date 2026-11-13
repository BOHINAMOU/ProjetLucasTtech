from django.urls import path

from . import views

app_name = 'concours'

urlpatterns = [
    path('', views.index, name='index'),
    path('lire/<str:kind>/<int:pk>/', views.reader, name='reader'),
    path('fichier/<str:kind>/<int:pk>/', views.file, name='file'),
    path('telecharger/<str:kind>/<int:pk>/', views.download, name='download'),
    path('<slug:slug>/', views.detail, name='detail'),
    path('<slug:slug>/<int:year>/', views.session, name='session'),
]
