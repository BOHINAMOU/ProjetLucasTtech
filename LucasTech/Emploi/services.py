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


def share_application(application):
    """Transmet le dossier du candidat à l'entreprise concernée. Retourne False s'il n'y a pas d'entreprise."""
    from django.utils import timezone
    employer = application.employer
    if not employer:
        return False
    if not application.shared_with_employer:
        application.shared_with_employer = True
        application.shared_at = timezone.now()
        newly_shortlisted = application.status == 'received'
        if newly_shortlisted:
            application.status = 'shortlisted'
        application.save()
        if newly_shortlisted:
            notify_application_status(application)
    target = application.offer or application.request
    notify(employer.user,
           f"Lantante vous transmet le dossier de {application.candidate.name} pour « {target} » (CV, contacts"
           + (", lettre de motivation" if application.cover_letter else "") + "). Analysez-le puis contactez le candidat.",
           '/emploi/mon-espace/')
    notify(application.candidate.user,
           f"Votre dossier pour « {target} » a été transmis à {employer.company_name}. L'entreprise peut vous contacter.",
           '/emploi/mon-espace/')
    return True


def notify_application_status(application):
    """Prévient le candidat (site + e-mail) quand le statut de sa candidature change."""
    target = application.offer or application.request
    extra = application.status_message.strip()
    status = application.status
    url = '/emploi/mon-espace/'
    if status == 'shortlisted':
        text = (f"Bonne nouvelle : vous êtes présélectionné(e) pour « {target} ». "
                "Connectez-vous et indiquez vos disponibilités pour l'entretien.")
        if extra:
            text += f"\n\n{extra}"
        url = f'/emploi/candidatures/{application.pk}/disponibilites/'
    elif status == 'interview':
        text = f"Votre entretien pour « {target} » est en cours d'organisation."
        if extra:
            text += f"\n\n{extra}"
        url = '/emploi/rendez-vous/'
    elif status == 'hired':
        text = f"Félicitations ! Votre candidature pour « {target} » est retenue : vous êtes embauché(e)."
        if extra:
            text += f"\n\n{extra}"
    elif status == 'refused':
        text = f"Votre candidature pour « {target} » n'a pas été retenue."
        text += f"\n\nMotif : {extra}" if extra else ""
        text += "\n\nMerci pour l'intérêt porté à ce poste : d'autres offres sont disponibles sur le site."
        url = '/emploi/offres/'
    else:
        return None
    return notify(application.candidate.user, text, url)


def decide_employer(employer, status):
    """Applique la décision de Lantante (acceptée / refusée) et prévient l'entreprise."""
    from django.utils import timezone
    if employer.status == status:
        return
    employer.status = status
    employer.decided_at = timezone.now()
    employer.save(update_fields=['status', 'decided_at'])
    extra = f"\n\n{employer.decision_message}" if employer.decision_message else ""
    if status == 'approved':
        notify(employer.user, "Bonne nouvelle : votre entreprise « %s » est acceptée. Vous pouvez déposer vos demandes "
               "de recrutement et vos offres autant de fois que nécessaire.%s" % (employer.company_name, extra),
               '/emploi/mon-espace/')
    elif status == 'rejected':
        notify(employer.user, "Votre demande d'inscription pour « %s » n'a pas été retenue.%s "
               "Vous pouvez corriger votre fiche et la renvoyer." % (employer.company_name, extra),
               '/emploi/mon-espace/')


def is_staff(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def can_browse_candidates(user):
    """L'annuaire des candidats est réservé à Lantante et aux entreprises acceptées."""
    if not user.is_authenticated:
        return False
    if is_staff(user):
        return True
    employer = getattr(user, 'employer_profile', None)
    return bool(employer and employer.is_approved)


def can_see_private(viewer, candidate):
    """Qui a le droit de voir le CV et les contacts d'un candidat ?

    - le candidat lui-même et l'équipe Lantante, toujours ;
    - une entreprise VÉRIFIÉE si le candidat l'a autorisé, ou si Lantante lui
      a transmis son dossier (candidature à une de ses offres, proposition).
    """
    if not viewer.is_authenticated:
        return False
    if viewer.pk == candidate.user_id or is_staff(viewer):
        return True
    employer = getattr(viewer, 'employer_profile', None)
    if not employer or not employer.is_approved:
        return False
    # Partage libre voulu par le candidat : réservé aux entreprises avec le badge bleu.
    if candidate.share_with_recruiters and employer.is_verified:
        return True
    # Candidature : le dossier n'est visible qu'après transmission par Lantante.
    return Application.objects.filter(candidate=candidate, shared_with_employer=True).filter(
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
