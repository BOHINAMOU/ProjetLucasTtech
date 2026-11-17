from django.urls import path

from . import views

app_name = 'repetiteurs'

urlpatterns = [
    path('devenir/', views.devenir, name='devenir'),
    path('ma-candidature/', views.ma_candidature, name='ma_candidature'),
    path('piece/<int:pk>/<str:cote>/', views.piece, name='piece'),
]
