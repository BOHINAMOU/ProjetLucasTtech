from django.urls import path
from . import app_page, conformite, history, views

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
    path('monetisation/', views.monetization_page, name='monetization'),
    path('monetisation/merci/', views.monetization_thanks, name='monetization_thanks'),
    path('historique/', history.history, name='history'),
    path('application/', app_page.application, name='application'),
    path('application/telecharger/', app_page.telecharger, name='application_download'),
    path('application/partenaire/', app_page.application_partenaire, name='application_partenaire'),
    path('application/partenaire/telecharger/', app_page.telecharger_partenaire, name='application_partenaire_download'),
    path('confidentialite/', views.privacy_policy, name='privacy_policy'),
    path('suppression-compte/', conformite.suppression_compte, name='suppression_compte'),
    path('signaler/', conformite.signaler, name='signaler'),
    path('conditions-utilisation/', views.terms_of_service, name='terms_of_service'),
    path('contact/', __import__('core.contact', fromlist=['contact']).contact, name='contact'),
]
