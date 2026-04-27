from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views

app_name = 'users'

urlpatterns = [

    # ───────── COMPTE ─────────
    path('inscription/', views.register, name='register'),
    path('profil/', views.profile, name='profile'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),

    # ───────── AUTH ─────────
    path(
        'connexion/',
        LoginView.as_view(template_name='users/login.html'),
        name='login'
    ),

    path(
        'deconnexion/',
        LogoutView.as_view(next_page='users:login'),
        name='logout'
    ),

    # ───────── RESET PASSWORD OTP FLOW ─────────

    # STEP 1 : email
    path('mot-de-passe/oublie/', views.password_reset_request, name='password_reset'),

    # PAGE INFO (email envoyé)
    path('mot-de-passe/email-envoye/', views.password_reset_email_sent, name='password_reset_email_sent'),

    # STEP 2 : code OTP
    path('mot-de-passe/verification/', views.password_reset_verify, name='password_reset_verify'),

    # STEP 3 : nouveau mot de passe
    path('mot-de-passe/nouveau/', views.password_reset_new_password, name='password_reset_new_password'),
]