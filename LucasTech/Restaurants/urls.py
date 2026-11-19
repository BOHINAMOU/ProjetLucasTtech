from django.urls import path

from . import views

app_name = "restaurants"
urlpatterns = [
    path("", views.liste, name="liste"),
    path("<slug:slug>/", views.detail, name="detail"),
    path("<slug:slug>/commander/", views.clic, name="clic"),
]
