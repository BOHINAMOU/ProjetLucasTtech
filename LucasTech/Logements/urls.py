from django.urls import path

from . import formulaires, views

app_name = "logements"
urlpatterns = [
    path("", views.liste, name="liste"),
    path("je-cherche/", formulaires.je_cherche, name="je_cherche"),
    path("publier/", formulaires.publier, name="publier"),
    path("<int:pk>/", views.detail, name="detail"),
]
