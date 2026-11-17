from django.urls import path

from . import views_vendre as v

app_name = 'vendre'

urlpatterns = [
    path('', v.vendre, name='demande'),
    path('dossier/<str:jeton>/', v.suivi, name='suivi'),
    path('dossier/<str:jeton>/modifier/', v.vendre, name='modifier'),
    path('piece/<int:pk>/', v.piece, name='piece'),
]
