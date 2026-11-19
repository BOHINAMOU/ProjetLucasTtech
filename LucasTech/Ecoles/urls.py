from django.urls import path

from . import views

app_name = 'ecoles'
urlpatterns = [
    path('', views.liste, name='liste'),
    path('<slug:slug>/', views.fiche, name='fiche'),
]
