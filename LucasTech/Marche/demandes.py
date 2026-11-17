"""Demandes « Vendre sur Lantante » : accepter (compte + espace vendeur), demander une correction, refuser."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Vendeur


def _site():
    return (getattr(settings, 'SITE_URL', '') or 'https://lantantetechnologie.com').rstrip('/')


def ecrire(d, sujet, texte):
    try:
        send_mail(sujet, f"Bonjour {d.prenom},\n\n{texte}\n\nDemande n° {d.numero}\nSuivi : {_site()}{d.get_absolute_url()}"
                         f"\n\nL'équipe Lantante", settings.DEFAULT_FROM_EMAIL, [d.email], fail_silently=True)
    except Exception:
        pass


def accepter(d, commission=None):
    """Crée (ou retrouve) le compte, la fiche vendeur validée et son accès à l'espace vendeur."""
    from .models import _jeton  # noqa: F401  (même module)
    User = get_user_model()
    with transaction.atomic():
        user = User.objects.filter(email__iexact=d.email).first()
        if not user:
            user = User.objects.create_user(email=d.email, password=None, first_name=d.prenom, last_name=d.nom)
            user.set_unusable_password()
            user.save()
        v = Vendeur.objects.filter(user=user).first() or Vendeur(user=user)
        v.boutique, v.whatsapp, v.ville, v.statut = d.boutique, d.whatsapp, d.ville, 'valide'
        if commission is not None:
            v.commission_pct = commission
        v.save()  # donne l'accès à l'espace vendeur
        d.vendeur, d.statut, d.motif, d.decide_le = v, 'acceptee', '', timezone.now()
        d.save(update_fields=['vendeur', 'statut', 'motif', 'decide_le', 'updated_at'])
    ecrire(d, "Bienvenue sur Lantante", "Votre boutique est acceptée.\n\n"
           f"1. Créez votre mot de passe : {_site()}/users/mot-de-passe/oublie/ (avec cette adresse e-mail).\n"
           f"2. Connectez-vous à votre espace vendeur : {_site()}/lantanteAdminTech/\n"
           "Vous y ajoutez vos produits, vos photos et vos propres catégories.")
    return v


def demander_correction(d, motif):
    d.statut, d.motif = 'a_corriger', motif
    d.save(update_fields=['statut', 'motif', 'updated_at'])
    ecrire(d, "Demande à corriger", f"Votre demande doit être corrigée :\n{motif}")


def refuser(d, motif):
    d.statut, d.motif, d.decide_le = 'refusee', motif, timezone.now()
    d.save(update_fields=['statut', 'motif', 'decide_le', 'updated_at'])
    ecrire(d, "Demande refusée", f"Votre demande n'a pas été retenue :\n{motif}")
