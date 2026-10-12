from django.urls import path

from . import views

urlpatterns = [
    path('config', views.config),

    # Compte
    path('auth/register', views.register),
    path('auth/login', views.login),
    path('auth/logout', views.logout),
    path('me', views.me),
    path('me/account-type', views.choose_account_type),
    path('devices', views.devices),
    path('dashboard', views.dashboard),

    # Public : offres, entreprises, partenaires, actualités
    path('offers', views.offers),
    path('offers/<slug:slug>', views.offer_detail),
    path('offers/<slug:slug>/apply', views.offer_apply),
    path('companies', views.companies),
    path('companies/<int:pk>', views.company_detail),
    path('partners', views.partners),
    path('partners/<int:pk>', views.partner_detail),
    path('partners/<int:pk>/message', views.partner_message),
    path('feed', views.feed),
    path('feed/<int:pk>/like', views.post_like),
    path('feed/<int:pk>/comments', views.post_comment),

    # Candidat
    path('candidate/profile', views.candidate_me),
    path('candidate/documents', views.candidate_documents),
    path('candidate/documents/<int:pk>', views.candidate_document_delete),
    path('candidate/applications', views.candidate_applications),
    path('candidate/applications/<int:pk>/availability', views.application_availability),
    path('candidate/applications/<int:pk>/consent', views.application_consent),
    path('candidate/requests', views.spontaneous_list),
    path('candidate/requests/<int:pk>', views.spontaneous_item),

    # Entreprise
    path('employer/profile', views.employer_me),
    path('employer/applications', views.employer_applications),
    path('employer/applications/<int:pk>', views.employer_application_detail),
    path('employer/applications/<int:pk>/decide', views.employer_decide),
    path('employer/applications/<int:pk>/schedule', views.employer_schedule),
    path('employer/offers', views.employer_offers),
    path('employer/offers/<slug:slug>/filled', views.offer_filled),
    path('candidates/<int:pk>', views.candidate_detail),

    # Publications payantes (entreprise et particulier)
    path('publish/plans', views.publish_plans),
    path('orders', views.orders),
    path('orders/<int:pk>', views.order_item),
    path('orders/<int:pk>/pay', views.order_pay),
    path('orders/<int:pk>/cancel', views.order_cancel),
    path('orders/<int:pk>/receipt', views.order_receipt),

    # Messagerie, rendez-vous, notifications
    path('conversations', views.conversations),
    path('conversations/<int:pk>', views.conversation_detail),
    path('conversations/<int:pk>/messages', views.conversation_send),
    path('appointments', views.appointments),
    path('appointments/<int:pk>/respond', views.appointment_respond),
    path('notifications', views.notifications),

    # Fichiers privés
    path('candidates/<int:pk>/cv', views.candidate_cv),
    path('documents/<int:pk>/file', views.document_file),
]
