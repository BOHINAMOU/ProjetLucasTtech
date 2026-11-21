"""Routes de Lantante Express, incluses sous /api/mobile/v1/courses/."""
from django.urls import path

from . import api, discussion

urlpatterns = [
    # Client
    path('categories/', api.categories, name='courses_categories'),
    path('estimation/', api.estimation, name='courses_estimation'),
    path('en-cours/', api.en_cours, name='courses_en_cours'),
    path('', api.courses, name='courses'),
    path('<int:pk>/', api.course, name='course'),
    path('<int:pk>/annuler/', api.annuler, name='course_annuler'),
    path('<int:pk>/noter/', api.noter, name='course_noter'),
    path('<int:pk>/signaler/', api.signaler, name='course_signaler'),
    path('<int:pk>/recu/', api.recu, name='course_recu'),
    # Discussion (client et partenaire de la course)
    path('<int:pk>/messages/', discussion.messages, name='course_messages'),
    path('<int:pk>/messages/lus/', discussion.lus, name='course_messages_lus'),
    path('<int:pk>/messages/<int:mid>/fichier/', discussion.fichier, name='course_message_fichier'),
    # Partenaire (application des coursiers, à venir)
    path('partenaire/', api.partenaire, name='partenaire_express'),
    path('partenaire/documents/', api.documents, name='partenaire_documents'),
    path('partenaire/changement-type/', api.changement_type, name='partenaire_changement_type'),
    path('partenaire/statut/', api.statut, name='partenaire_statut'),
    path('partenaire/position/', api.position, name='partenaire_position'),
    path('partenaire/offre/', api.offre, name='partenaire_offre'),
    path('partenaire/offres/<int:pk>/<str:action>/', api.offre_reponse, name='partenaire_offre_reponse'),
    path('partenaire/courses/', api.partenaire_courses, name='partenaire_courses'),
    path('partenaire/courses/<int:pk>/<str:action>/', api.course_action, name='partenaire_course_action'),
    path('partenaire/solde/', api.partenaire_solde, name='partenaire_solde'),
]
