from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('partenaires/', views.partners_page, name='partners'),
    path('partenaires/devenir-partenaire/', views.partner_apply, name='partner_apply'),
    path('partenaires/devenir-partenaire/merci/', views.partner_apply_success, name='partner_apply_success'),
    path('partenaires/<int:pk>/', views.partner_detail, name='partner_detail'),
    path('projets/', views.projects_page, name='projects'),
    path('projets/<int:pk>/', views.project_detail, name='project_detail'),
    path('equipe/', views.team_page, name='team'),
    path('equipe/<int:pk>/', views.team_member_detail, name='team_member_detail'),
    path('confidentialite/', views.privacy_policy, name='privacy_policy'),
    path('conditions-utilisation/', views.terms_of_service, name='terms_of_service'),
]
