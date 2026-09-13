from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('partenaires/', views.partners_page, name='partners'),
    path('projets/', views.projects_page, name='projects'),
    path('equipe/', views.team_page, name='team'),
]
