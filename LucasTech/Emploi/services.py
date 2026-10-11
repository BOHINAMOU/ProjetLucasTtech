import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Q

from .models import Application, CandidateProfile, Notification


SITE_URL = 'https://lantantetechnologie.com'
logger = logging.getLogger(__name__)


def notify(user, text, url='', email=True):
    """Crée la notification sur le site et envoie aussi un e-mail (sans jamais bloquer l'action)."""
    notification = Notification.objects.create(recipient=user, text=text[:300], url=url)
    if email and user.email and settings.EMAIL_HOST_USER:
        link = url if url.startswith('http') else f"{SITE_URL}{url or '/emploi/notifications/'}"
        try:
            send_mail(
                subject="Lantante Technologie — Emploi",
                message=f"{text}\n\nOuvrir : {link}\n\n— Lantante Technologie",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            logger.exception("Échec d'envoi de l'e-mail de notification")
    return notification


def notify_staff(text, url=''):
    """Prévient toute l'équipe Lantante (comptes administrateurs actifs)."""
    User = get_user_model()
    for staff in User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True)):
        notify(staff, text, url)


def is_staff(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def can_see_private(viewer, candidate):
    """Qui a le droit de voir le CV et les contacts d'un candidat ?

    - le candidat lui-même et l'équipe Lantante, toujours ;
    - une entreprise VÉRIFIÉE si le candidat l'a autorisé, ou s'il a postulé
      à une de ses offres / a été proposé pour une de ses demandes.
    """
    if not viewer.is_authenticated:
        return False
    if viewer.pk == candidate.user_id or is_staff(viewer):
        return True
    employer = getattr(viewer, 'employer_profile', None)
    if not employer or not employer.is_verified:
        return False
    if candidate.share_with_recruiters:
        return True
    return Application.objects.filter(candidate=candidate).filter(
        Q(offer__employer=employer) | Q(request__employer=employer)
    ).exists()


def score_candidate(candidate, domain, skill_ids, city):
    """Note de 0 à 100 : domaine (40) + compétences (40) + ville (20)."""
    score, reasons = 0, []
    if candidate.domain == domain:
        score += 40
        reasons.append("même domaine")
    if skill_ids:
        common = set(candidate.skills.values_list('id', flat=True)) & set(skill_ids)
        if common:
            score += round(40 * len(common) / len(skill_ids))
            reasons.append(f"{len(common)}/{len(skill_ids)} compétence(s)")
    if city and candidate.city and candidate.city.strip().lower() == city.strip().lower():
        score += 20
        reasons.append("même ville")
    return score, reasons


def suggest_candidates(target, limit=30):
    """Candidats suggérés pour une offre ou une demande de recrutement."""
    skill_ids = list(target.skills.values_list('id', flat=True))
    already = set(Application.objects.filter(
        **({'offer': target} if hasattr(target, 'slug') else {'request': target})
    ).values_list('candidate_id', flat=True))
    results = []
    for cand in CandidateProfile.objects.filter(is_published=True, available=True).select_related('user'):
        if cand.pk in already:
            continue
        score, reasons = score_candidate(cand, target.domain, skill_ids, target.city)
        # La ville seule ne suffit pas : il faut au moins le domaine ou une compétence.
        if score > 0 and reasons != ["même ville"]:
            results.append({'candidate': cand, 'score': score, 'reasons': ", ".join(reasons)})
    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:limit]
