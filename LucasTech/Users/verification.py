"""Vérification de l'adresse e-mail à l'inscription (site et application).

Un code à 6 chiffres est envoyé par e-mail. Tant qu'il n'est pas saisi, le compte reste « non vérifié » :
connexion impossible, donc aucun achat. Code valable 15 minutes, 5 essais par code, renvoi possible
au bout de 60 secondes."""
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)

CODE_TTL = timedelta(minutes=15)
RESEND_DELAY = timedelta(seconds=60)
MAX_ATTEMPTS = 5


def is_verified(user):
    """Comptes de l'équipe et comptes Google (adresse déjà vérifiée par Google) : vérifiés d'office."""
    if user is None:
        return False
    if user.is_verified or user.is_staff or user.is_superuser:
        return True
    social = getattr(user, 'social_auth', None)
    return bool(social is not None and social.exists())


def _new_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def resend_wait(user):
    """Secondes à attendre avant de pouvoir renvoyer un code (0 = possible tout de suite)."""
    last = user.email_codes.order_by('-created_at').first()
    if not last:
        return 0
    left = (last.created_at + RESEND_DELAY - timezone.now()).total_seconds()
    return max(0, int(left + 0.999))


def send_code(user, force=False):
    """Crée et envoie un nouveau code. Renvoie False si le dernier a été envoyé il y a moins de 60 s."""
    if not force and resend_wait(user) > 0:
        return False
    from .models import EmailVerificationCode
    user.email_codes.filter(is_used=False).update(is_used=True)  # un seul code valable à la fois
    otp = EmailVerificationCode.objects.create(user=user, code=_new_code())
    prenom = user.first_name or user.email
    try:
        send_mail(
            subject="Votre code de vérification — Lantante Technologie",
            message=(f"Bonjour {prenom},\n\n"
                     f"Pour activer votre compte Lantante Technologie, saisissez ce code :\n\n"
                     f"    {otp.code}\n\n"
                     "Il est valable 15 minutes.\n\n"
                     "Si vous n'avez pas créé de compte, ignorez simplement ce message : "
                     "personne ne pourra utiliser votre adresse sans ce code.\n"),
            from_email=settings.DEFAULT_FROM_EMAIL, recipient_list=[user.email], fail_silently=False)
    except Exception:
        logger.exception("Échec d'envoi du code de vérification à %s", user.email)
    return True


def check_code(user, code):
    """Vérifie le code. Renvoie (True, '') et marque le compte vérifié, ou (False, message d'erreur)."""
    code = (code or '').strip().replace(' ', '')
    otp = user.email_codes.filter(is_used=False).order_by('-created_at').first()
    if not otp or timezone.now() > otp.created_at + CODE_TTL:
        return False, "Ce code a expiré. Demandez un nouveau code."
    if otp.attempts >= MAX_ATTEMPTS:
        return False, "Trop d'essais avec ce code. Demandez un nouveau code."
    if not secrets.compare_digest(otp.code, code):
        otp.attempts += 1
        otp.save(update_fields=['attempts'])
        left = MAX_ATTEMPTS - otp.attempts
        return False, (f"Code incorrect. Il vous reste {left} essai{'s' if left > 1 else ''}."
                       if left else "Trop d'essais avec ce code. Demandez un nouveau code.")
    otp.is_used = True
    otp.save(update_fields=['is_used'])
    mark_verified(user)
    return True, ''


def mark_verified(user):
    if not user.is_verified or not user.is_active:
        user.is_verified = True
        user.is_active = True
        user.save(update_fields=['is_verified', 'is_active'])


def reusable_unverified(email):
    """Compte jamais vérifié avec cette adresse : on peut le « reprendre » à l'inscription
    (sinon quelqu'un pourrait bloquer l'adresse d'un autre en s'inscrivant le premier)."""
    from .models import User
    u = User.objects.filter(email__iexact=email).first()
    if u and not is_verified(u) and not u.last_login:
        return u
    return None


def social_mark_verified(backend, user=None, *args, **kwargs):
    """Étape du pipeline social_django : un compte Google a une adresse déjà vérifiée."""
    if user is not None and not user.is_verified:
        mark_verified(user)
