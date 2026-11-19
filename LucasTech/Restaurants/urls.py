from django.urls import path

from . import views

app_name = "restaurants"
urlpatterns = [
    path("", views.liste, name="liste"),
    path("credits-photos/", views.credits_photos, name="credits"),
    path("<slug:slug>/", views.detail, name="detail"),
    path("<slug:slug>/commander/", views.clic, name="clic"),
]
