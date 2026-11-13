import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from . import verification
from .models import PasswordResetCode
from .forms import RegisterForm, LoginForm, SetNewPasswordForm, ProfileUpdateForm

User = get_user_model()
logger = logging.getLogger(__name__)


# ─────────────────────────────
#  REGISTER
# ─────────────────────────────
def _safe_next(request):
    """Adresse « next » (retour après inscription), uniquement si elle reste sur ce site."""
    target = request.POST.get('next') or request.GET.get('next') or ''
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                                  require_https=request.is_secure()):
        return target
    return ''


class SiteLoginView(LoginView):
    """Après connexion, un candidat ou une entreprise arrive directement dans son propre espace.
    Un compte dont l'e-mail n'est pas encore vérifié est renvoyé vers la saisie du code."""

    def get_default_redirect_url(self):
        return super().get_default_redirect_url()

    def form_invalid(self, form):
        uid = getattr(form, 'unverified_user_id', None)
        if uid:
            self.request.session['verify_user_id'] = uid
            user = User.objects.get(pk=uid)
            verification.send_code(user)
            nxt = _safe_next(self.request)
            return redirect(reverse('users:verify_email') + (f'?next={nxt}' if nxt else ''))
        return super().form_invalid(form)


def register(request):
    next_url = _safe_next(request)
    if request.user.is_authenticated:
        return redirect(next_url or 'core:home')

    form = RegisterForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        # Compte jamais vérifié avec la même adresse : on le reprend (sinon l'adresse resterait bloquée).
        old = verification.reusable_unverified(form.cleaned_data['email'])
        if old:
            old.delete()
        user = form.save(commit=False)
        user.account_type = 'member'
        user.is_verified = False
        user.save()
        verification.send_code(user, force=True)
        request.session['verify_user_id'] = user.pk
        return redirect(reverse('users:verify_email') + (f'?next={next_url}' if next_url else ''))

    return render(request, 'users/register.html', {'form': form, 'next': next_url})


def verify_email(request):
    """Saisie du code à 6 chiffres reçu par e-mail (après l'inscription ou une connexion non vérifiée)."""
    uid = request.session.get('verify_user_id')
    user = User.objects.filter(pk=uid).first() if uid else None
    if not user:
        return redirect('users:register')
    next_url = _safe_next(request)
    if verification.is_verified(user):
        request.session.pop('verify_user_id', None)
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect(next_url or 'core:home')
    error = ''
    if request.method == 'POST':
        if request.POST.get('action') == 'renvoyer':
            if verification.send_code(user):
                messages.success(request, "Un nouveau code vient d'être envoyé.")
            else:
                error = f"Patientez encore {verification.resend_wait(user)} secondes avant de renvoyer un code."
        else:
            ok, error = verification.check_code(user, request.POST.get('code'))
            if ok:
                request.session.pop('verify_user_id', None)
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, f'Bienvenue {user.first_name or user.email} ! Votre compte est activé.')
                return redirect(next_url or 'core:home')
    return render(request, 'users/verify_email.html', {
        'email': user.email, 'error': error, 'next': next_url, 'wait': verification.resend_wait(user)})


# ─────────────────────────────
#  LOGIN
# ─────────────────────────────
def user_login(request):
    if request.user.is_authenticated:
        return redirect('core:home')

    form = LoginForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        if not verification.is_verified(user):
            request.session['verify_user_id'] = user.pk
            verification.send_code(user)
            return redirect('users:verify_email')
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Bon retour, {user.email} !')
        return redirect('core:home')

    return render(request, 'users/login.html', {'form': form})


# ─────────────────────────────
#  LOGOUT
# ─────────────────────────────
def user_logout(request):
    logout(request)
    return redirect('core:home')


# ─────────────────────────────
#  STEP 1 — SEND OTP (CORRIGÉ)
# ─────────────────────────────
def password_reset_request(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        user = User.objects.filter(email__iexact=email).first()

        if not user:
            messages.error(request, "Aucun compte n'est associé à cette adresse email.")
            return redirect("users:password_reset")

        otp = PasswordResetCode.objects.create(
            user=user,
            code=PasswordResetCode.generate_code()
        )

        message = f"""
Bonjour {user.email},

Vous avez demandé une réinitialisation de mot de passe.

CODE DE VÉRIFICATION : {otp.code}

Ce code est valable 5 minutes.

⚠️ Ne partagez jamais ce code.
"""

        try:
            send_mail(
                subject="Réinitialisation de mot de passe - Lantante Technologie",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception:
            logger.exception("Échec d'envoi de l'email de réinitialisation")
            messages.error(
                request,
                "Le service d'envoi d'email est momentanément indisponible. "
                "Réessayez plus tard ou contactez le support."
            )
            return redirect("users:password_reset")

        # IMPORTANT : stocker session
        request.session["reset_user_id"] = user.id
        request.session["reset_attempts"] = 0

        return redirect("users:password_reset_email_sent")

    return render(request, "users/password_reset.html")


# ─────────────────────────────
#  EMAIL SENT PAGE
# ─────────────────────────────
def password_reset_email_sent(request):
    return render(request, "users/password_reset_email_sent.html")


# ─────────────────────────────
#  STEP 2 — VERIFY OTP
# ─────────────────────────────
def password_reset_verify(request):
    user_id = request.session.get("reset_user_id")

    if not user_id:
        messages.error(request, "Session expirée. Recommencez.")
        return redirect("users:password_reset")

    user = get_object_or_404(User, id=user_id)

    MAX_ATTEMPTS = 5

    if request.method == "POST":
        attempts = request.session.get("reset_attempts", 0)

        if attempts >= MAX_ATTEMPTS:
            request.session.flush()
            messages.error(request, "Trop de tentatives. Recommencez la procédure.")
            return redirect("users:password_reset")

        code = request.POST.get("code", "").strip()

        otp = PasswordResetCode.objects.filter(
            user=user,
            code=code,
            is_used=False
        ).first()

        if not otp or not otp.is_valid():
            request.session["reset_attempts"] = attempts + 1
            remaining = MAX_ATTEMPTS - (attempts + 1)
            if remaining <= 0:
                request.session.flush()
                messages.error(request, "Trop de tentatives. Recommencez la procédure.")
                return redirect("users:password_reset")
            messages.error(request, f"Code invalide ou expiré ({remaining} tentative(s) restante(s))")
            return redirect("users:password_reset_verify")

        otp.is_used = True
        otp.save()

        request.session["otp_verified"] = True

        return redirect("users:password_reset_new_password")

    return render(request, "users/password_reset_verify.html")


# ─────────────────────────────
#  STEP 3 — NEW PASSWORD
# ─────────────────────────────
def password_reset_new_password(request):
    user_id = request.session.get("reset_user_id")

    if not user_id or not request.session.get("otp_verified"):
        messages.error(request, "Accès non autorisé.")
        return redirect("users:password_reset")

    user = get_object_or_404(User, id=user_id)

    form = SetNewPasswordForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user.set_password(form.cleaned_data["new_password1"])
        user.is_verified = True  # le code reçu par e-mail prouve que l'adresse lui appartient
        user.save()

        request.session.flush()

        messages.success(request, "Mot de passe modifié avec succès")
        return redirect("users:login")

    return render(request, "users/password_reset_new_password.html", {"form": form})


# ─────────────────────────────
#  PROFILE
# ─────────────────────────────
@login_required
def profile(request):
    from abonnements.access import accessible_contest_ids, active_subscriptions, has_unlimited
    from Payments.models import Payment
    u = request.user
    paid = Payment.objects.filter(user=u, status='approved')
    stats = {
        'subs': active_subscriptions(u).count(),
        'contests': 'Tous' if has_unlimited(u) else len(accessible_contest_ids(u)),
        'purchases': paid.exclude(kind__in=['ticket', 'abonnement']).count(),
        'tickets': paid.filter(kind='ticket').count(),
    }
    return render(request, 'users/profile.html', {'user': u, 'stats': stats})


@login_required
def edit_profile(request):
    form = ProfileUpdateForm(request.POST or None, instance=request.user)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Profil mis à jour")
        return redirect('users:profile')

    return render(request, 'users/edit_profile.html', {'form': form})