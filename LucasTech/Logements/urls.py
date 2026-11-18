from django.urls import path

from . import views

app_name = "logements"
urlpatterns = [
    path("", views.liste, name="liste"),
    path("<int:pk>/", views.detail, name="detail"),
]
