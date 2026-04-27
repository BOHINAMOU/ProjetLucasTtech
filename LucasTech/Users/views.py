from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings

from .models import PasswordResetCode
from .forms import RegisterForm, LoginForm, SetNewPasswordForm, ProfileUpdateForm

User = get_user_model()


# ─────────────────────────────
# 📝 REGISTER
# ─────────────────────────────
def register(request):
    if request.user.is_authenticated:
        return redirect('core:home')

    form = RegisterForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Bienvenue {user.email} ! Compte créé avec succès.')
        return redirect('core:home')

    return render(request, 'users/register.html', {'form': form})


# ─────────────────────────────
# 🔐 LOGIN
# ─────────────────────────────
def user_login(request):
    if request.user.is_authenticated:
        return redirect('core:home')

    form = LoginForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Bon retour, {user.email} !')
        return redirect('core:home')

    return render(request, 'users/login.html', {'form': form})


# ─────────────────────────────
# 🚪 LOGOUT
# ─────────────────────────────
def user_logout(request):
    logout(request)
    return redirect('core:home')


# ─────────────────────────────
# 📩 STEP 1 — SEND OTP
# ─────────────────────────────
def password_reset_request(request):
    if request.method == "POST":
        email = request.POST.get("email")

        user = User.objects.filter(email=email).first()

        # 🔐 Toujours répondre pareil (sécurité)
        if user:
            otp = PasswordResetCode.objects.create(
                user=user,
                code=PasswordResetCode.generate_code()
            )

            # ✉️ MESSAGE EMAIL PRO
            message = f"""
Bonjour {user.email},

Vous avez demandé à réinitialiser votre mot de passe sur LucasTech.

CODE DE VÉRIFICATION : {otp.code}

 Ce code est valable pendant 5 minutes.

⚠️ IMPORTANT :
- Ne partagez jamais ce code avec qui que ce soit.
- LucasTech ne vous demandera jamais ce code.

Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.

Cordialement,
— L'équipe LucasTech 
"""

            send_mail(
                subject="Réinitialisation de mot de passe - LucasTech",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            request.session["reset_user_id"] = user.id

        messages.success(request, "Un email contenant un code de vérification vous a été envoyé.")
        return redirect("users:password_reset_email_sent")

    return render(request, "users/password_reset.html")


# ─────────────────────────────
# 📩 EMAIL SENT PAGE
# ─────────────────────────────
def password_reset_email_sent(request):
    return render(request, "users/password_reset_email_sent.html")


# ─────────────────────────────
# 🔐 STEP 2 — VERIFY CODE
# ─────────────────────────────
def password_reset_verify(request):
    user_id = request.session.get("reset_user_id")

    if not user_id:
        return redirect("users:password_reset")

    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        code = request.POST.get("code")

        otp = PasswordResetCode.objects.filter(
            user=user,
            code=code,
            is_used=False
        ).first()

        if not otp or not otp.is_valid():
            messages.error(request, "Code invalide ou expiré")
            return redirect("users:password_reset_verify")

        otp.is_used = True
        otp.save()

        request.session["otp_verified"] = True

        return redirect("users:password_reset_new_password")

    return render(request, "users/password_reset_verify.html")


# ─────────────────────────────
# 🔐 STEP 3 — NEW PASSWORD
# ─────────────────────────────
def password_reset_new_password(request):
    user_id = request.session.get("reset_user_id")

    if not user_id or not request.session.get("otp_verified"):
        return redirect("users:password_reset")

    user = get_object_or_404(User, id=user_id)

    form = SetNewPasswordForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user.set_password(form.cleaned_data["new_password1"])
        user.save()

        request.session.flush()

        messages.success(request, "Mot de passe modifié avec succès")
        return redirect("users:login")

    return render(request, "users/password_reset_new_password.html", {"form": form})


# ─────────────────────────────
# 👤 PROFILE
# ─────────────────────────────
@login_required
def profile(request):
    return render(request, 'users/profile.html', {'user': request.user})


@login_required
def edit_profile(request):
    form = ProfileUpdateForm(request.POST or None, instance=request.user)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Profil mis à jour")
        return redirect('users:profile')

    return render(request, 'users/edit_profile.html', {'form': form})