from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "logements"
urlpatterns = [
    path("", views.liste, name="liste"),
    # « Je cherche » et « Publier mon logement » : retirés de l'interface (les demandes déjà reçues restent dans l'admin)
    path("je-cherche/", RedirectView.as_view(pattern_name='logements:liste'), name="je_cherche"),
    path("publier/", RedirectView.as_view(pattern_name='logements:liste'), name="publier"),
    path("<int:pk>/", views.detail, name="detail"),
    path("credits-photos/", views.credits_photos, name="credits"),
]
