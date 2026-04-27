"""from django.urls import path
from . import views
app_name = 'services'
urlpatterns = [
    path('services/', views.services, name='services')
    ]
"""""
from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    path('',           views.services,       name='services'),
    path('<int:pk>/',  views.service_detail, name='service_detail'),
]