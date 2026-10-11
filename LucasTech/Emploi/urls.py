from django.urls import path
from . import views

app_name = 'emploi'

urlpatterns = [
    path('', views.home, name='home'),

    # Offres
    path('offres/', views.offer_list, name='offer_list'),
    path('offres/<slug:slug>/', views.offer_detail, name='offer_detail'),
    path('offres/<slug:slug>/postuler/', views.offer_apply, name='offer_apply'),
    path('offres/<slug:slug>/pourvue/', views.offer_filled, name='offer_filled'),

    # Candidats
    path('candidats/', views.candidate_list, name='candidate_list'),
    path('candidats/<int:pk>/', views.candidate_detail, name='candidate_detail'),
    path('candidats/<int:pk>/cv/', views.cv_download, name='cv_download'),
    path('mon-espace/documents/', views.documents, name='documents'),
    path('tarifs/', views.pricing, name='pricing'),
    path('demandes/', views.spontaneous_list, name='spontaneous_list'),
    path('demandes/nouvelle/', views.spontaneous_new, name='spontaneous_new'),
    path('demandes/<int:pk>/modifier/', views.spontaneous_edit, name='spontaneous_edit'),
    path('demandes/<int:pk>/retirer/', views.spontaneous_withdraw, name='spontaneous_withdraw'),
    path('candidatures/<int:pk>/accord/', views.consent_respond, name='consent_respond'),
    path('mon-espace/publier/', views.publish_hub, name='publish_hub'),
    path('candidatures-recues/', views.applications_received, name='applications_received'),
    path('candidatures-recues/<int:pk>/decider/', views.application_decide, name='application_decide'),
    path('candidatures-recues/<int:pk>/entretien/', views.application_schedule, name='application_schedule'),
    path('mon-espace/publier/<slug:code>/', views.order_new, name='order_new'),
    path('commandes/<int:pk>/', views.order_detail, name='order_detail'),
    path('commandes/<int:pk>/payer/', views.order_pay, name='order_pay'),
    path('commandes/<int:pk>/modifier/', views.order_edit, name='order_edit'),
    path('commandes/<int:pk>/recu/', views.order_receipt, name='order_receipt'),
    path('commandes/<int:pk>/annuler/', views.order_cancel, name='order_cancel'),
    path('documents/<int:pk>/supprimer/', views.document_delete, name='document_delete'),
    path('documents/<int:pk>/', views.document_download, name='document_download'),

    # Entreprises
    path('entreprises/', views.company_list, name='company_list'),
    path('entreprises/<int:pk>/', views.company_detail, name='company_detail'),
    path('entreprises/<int:pk>/document/', views.employer_document, name='employer_document'),

    # Mon espace
    path('mon-espace/', views.dashboard, name='dashboard'),
    path('mon-espace/particulier/', views.choose_member, name='choose_member'),
    path('mon-espace/profil-candidat/', views.candidate_edit, name='candidate_edit'),
    path('mon-espace/entreprise/', views.employer_edit, name='employer_edit'),
    path('mon-espace/nouvelle-offre/', views.offer_create, name='offer_create'),
    path('mon-espace/demande-recrutement/', views.request_create, name='request_create'),

    # Fil d'actualités
    path('actualites/', views.feed, name='feed'),
    path('actualites/<int:pk>/aime/', views.post_like, name='post_like'),
    path('actualites/<int:pk>/commenter/', views.post_comment, name='post_comment'),
    path('actualites/<int:pk>/supprimer/', views.post_delete, name='post_delete'),

    # Messagerie, rendez-vous, notifications
    path('messages/', views.inbox, name='inbox'),
    path('messages/lantante/', views.contact_lantante, name='contact_lantante'),
    path('messages/nouveau/<int:user_id>/', views.new_conversation, name='new_conversation'),
    path('messages/<int:pk>/', views.conversation, name='conversation'),
    path('messages/<int:pk>/reprendre/', views.conversation_take, name='conversation_take'),
    path('candidatures/<int:pk>/disponibilites/', views.availability, name='availability'),
    path('rendez-vous/', views.appointments, name='appointments'),
    path('rendez-vous/<int:pk>/repondre/', views.appointment_respond, name='appointment_respond'),
    path('notifications/', views.notifications, name='notifications'),
]
