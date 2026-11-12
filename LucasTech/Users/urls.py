from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

from . import views


def fresh(view):
    """Formulaire sensible : jamais mis en cache (ni navigateur ni « Précédent ») et cookie CSRF garanti,
    sinon un jeton périmé (après connexion / déconnexion) provoque « La vérification CSRF a échoué »."""
    return never_cache(ensure_csrf_cookie(view))
from .forms import SiteAuthenticationForm

app_name = 'users'

urlpatterns = [

    # ───────── COMPTE ─────────
    path('inscription/', fresh(views.register), name='register'),
    path('profil/', never_cache(views.profile), name='profile'),
    path('edit-profile/', never_cache(views.edit_profile), name='edit_profile'),

    # ───────── AUTH ─────────
    path(
        'connexion/',
        fresh(views.SiteLoginView.as_view(template_name='users/login.html', authentication_form=SiteAuthenticationForm)),
        name='login'
    ),

    path(
        'deconnexion/',
        LogoutView.as_view(next_page='users:login'),
        name='logout'
    ),

    # ───────── RESET PASSWORD OTP FLOW ─────────

    # STEP 1 : email
    path('mot-de-passe/oublie/', fresh(views.password_reset_request), name='password_reset'),

    # PAGE INFO (email envoyé)
    path('mot-de-passe/email-envoye/', views.password_reset_email_sent, name='password_reset_email_sent'),

    # STEP 2 : code OTP
    path('mot-de-passe/verification/', fresh(views.password_reset_verify), name='password_reset_verify'),

    # STEP 3 : nouveau mot de passe
    path('mot-de-passe/nouveau/', fresh(views.password_reset_new_password), name='password_reset_new_password'),
]