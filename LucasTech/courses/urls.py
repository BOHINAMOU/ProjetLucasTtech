"""Routes de Lantante Express, incluses sous /api/mobile/v1/courses/."""
from django.urls import path

from . import api, discussion, pin

urlpatterns = [
    # Client
    path('categories/', api.categories, name='courses_categories'),
    path('estimation/', api.estimation, name='courses_estimation'),
    path('en-cours/', api.en_cours, name='courses_en_cours'),
    path('zone/', api.zone, name='courses_zone'),
    path('solde-suffisant/', api.solde_suffisant, name='courses_solde_suffisant'),
    # Code PIN du solde (client et partenaire)
    path('pin/', pin.etat, name='pin_etat'),
    path('pin/creer/', pin.creer, name='pin_creer'),
    path('pin/verifier/', pin.verifier, name='pin_verifier'),
    path('pin/oublie/', pin.oublie, name='pin_oublie'),
    path('pin/reinitialiser/', pin.reinitialiser, name='pin_reinitialiser'),
    path('proches/', api.proches, name='courses_proches'),
    path('', api.courses, name='courses'),
    path('<int:pk>/', api.course, name='course'),
    path('<int:pk>/annuler/', api.annuler, name='course_annuler'),
    path('<int:pk>/noter/', api.noter, name='course_noter'),
    path('<int:pk>/signaler/', api.signaler, name='course_signaler'),
    path('<int:pk>/recu/', api.recu, name='course_recu'),
    path('<int:pk>/favori/', api.favori, name='course_favori'),
    path('favoris/', api.favoris, name='courses_favoris'),
    path('favoris/<int:partenaire_id>/', api.retirer_favori, name='courses_favori_retirer'),
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
    path('partenaire/versement/', api.versement, name='partenaire_versement'),
]
