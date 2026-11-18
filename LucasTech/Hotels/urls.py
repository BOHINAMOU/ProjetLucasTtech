from django.urls import path

from . import views

app_name = "hotels"
urlpatterns = [
    path("", views.liste, name="liste"),
    path("<slug:slug>/", views.detail, name="detail"),
]
