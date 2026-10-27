from django.urls import path
from . import views

app_name = 'portfolio'

urlpatterns = [
    path('', views.home, name='home'),
    path('contact/', views.contact, name='contact'),
    path('projets/<slug:slug>/', views.project_detail, name='project_detail'),
    path('collaborateurs/<int:pk>/', views.collaborator_detail, name='collaborator_detail'),
]
