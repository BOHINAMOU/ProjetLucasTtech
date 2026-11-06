from django.urls import path

from . import views

app_name = 'events'

urlpatterns = [
    path('', views.event_list, name='list'),
    path('organisateur/', views.organizer_home, name='organizer'),
    path('organisateur/<slug:slug>/', views.organizer_event, name='organizer_event'),
    path('<slug:slug>/', views.event_detail, name='detail'),
]
