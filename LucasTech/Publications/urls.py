from django.urls import path
from . import views

app_name = 'publications'

urlpatterns = [
    path('',          views.publications,        name='publications'),
    path('<slug:slug>/', views.publication_detail, name='publication_detail'),
    path('<slug:slug>/commenter/', views.publication_comment, name='publication_comment'),
    path('<slug:slug>/message/', views.publication_quick_message, name='publication_quick_message'),
    path('<slug:slug>/inscription/',       views.publication_register,         name='publication_register'),
    path('<slug:slug>/inscription/merci/', views.publication_register_success, name='publication_register_success'),
]