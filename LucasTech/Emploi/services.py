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
    notification = Notification.objects.create(recipient=user, text=text, url=url)
    try:
        from .push import send_push
        send_push(user, "Lantante Technologie", text.split('\n')[0], url)
    except Exception:
        logger.warning("Notification push impossible", exc_info=True)
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
    for staff in staff_users():
        notify(staff, text, url)


def share_application(application):
    """Transmet le dossier du candidat à l'entreprise concernée. Retourne False s'il n'y a pas d'entreprise."""
    from django.utils import timezone
    employer = application.employer
    if not employer or application.consent != 'accepted':
        return False  # pas d'entreprise, ou le candidat n'a pas (encore) donné son accord
    if not application.shared_with_employer:
        application.shared_with_employer = True
        application.shared_at = timezone.now()
        newly_shortlisted = application.status == 'received'
        if newly_shortlisted:
            application.status = 'shortlisted'
        application.save()
        if newly_shortlisted:
            notify_application_status(application)
    if application.spontaneous_id:
        spontaneous = application.spontaneous
        spontaneous.status = 'transmitted'
        spontaneous.save(update_fields=['status', 'updated_at'])
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


# ── Service client : accusé de réception, présentation et changement d'interlocuteur
AUTO_ACK = (
    "Bonjour, nous vous remercions d'avoir contacté Lantante Technologie.\n\n"
    "Nous avons bien reçu votre message. Un membre de notre équipe vous répondra dès que possible.\n\n"
    "Merci pour votre confiance."
)


def staff_full_name(user):
    return user.get_full_name().strip() or "un membre de l'équipe"


def staff_title(user):
    return getattr(getattr(user, 'staff_profile', None), 'job_title', '')


def intro_text(staff):
    """Présentation du collaborateur : son identité vient de son propre compte, jamais d'un autre."""
    name, title = staff_full_name(staff), staff_title(staff)
    who = f"{name}, {title}" if title else name
    return (
        "Bonjour Monsieur/Madame,\n\n"
        f"Je me présente, {who}, membre de l'équipe de Lantante Technologie. Je prends en charge votre demande "
        "et serai votre interlocuteur pour la suite de nos échanges.\n\n"
        "Merci pour votre confiance.\n\n"
        f"Cordialement,\n{name}\nLantante Technologie"
    )


def post_auto_message(conversation, body):
    from .models import Message
    return Message.objects.create(conversation=conversation, sender=None, body=body, is_automatic=True)


def send_auto_ack(conversation):
    """Accusé de réception : une seule fois par conversation."""
    if conversation.auto_reply_sent:
        return None
    msg = post_auto_message(conversation, AUTO_ACK)
    conversation.auto_reply_sent = True
    conversation.save(update_fields=['auto_reply_sent'])
    return msg


def send_intro(conversation, staff):
    """Premier message humain : le collaborateur est présenté automatiquement, sous son identité réelle."""
    from .models import Message
    if conversation.intro_sent:
        return None
    msg = Message.objects.create(conversation=conversation, sender=staff, body=intro_text(staff), is_intro=True)
    msg.read_by.add(staff)
    conversation.intro_sent = True
    conversation.save(update_fields=['intro_sent'])
    return msg


def assign_conversation(conversation, staff):
    """Attribue la conversation à un collaborateur ; informe le candidat si l'interlocuteur change."""
    previous = conversation.assigned_to
    if previous and previous.pk == staff.pk:
        return
    conversation.assigned_to = staff
    conversation.status = 'assigned'
    conversation.intro_sent = False  # le nouveau collaborateur se présentera à sa première réponse
    conversation.save(update_fields=['assigned_to', 'status', 'intro_sent'])
    name, title = staff_full_name(staff), staff_title(staff)
    who = f"{name} ({title})" if title else name
    url = f"/emploi/messages/{conversation.pk}/"
    if previous:
        post_auto_message(
            conversation,
            f"Votre interlocuteur change : {who} reprend votre demande à la place de {staff_full_name(previous)}. "
            "Il se présentera dans son prochain message.")
        text = f"Changement d'interlocuteur : {who} reprend votre demande."
    else:
        text = f"{who} prend en charge votre demande."
    for person in conversation.requesters():
        notify(person, text, url)


# ── Modération : avertissements (3 maximum) puis bannissement
MAX_WARNINGS = 3


def active_warning_count(user):
    return user.moderation_warnings.filter(is_active=True).count()


def can_sanction(user):
    """L'équipe Lantante ne peut être ni avertie ni bannie depuis l'outil de modération."""
    return not (user.is_staff or user.is_superuser)


def apply_warning(warning):
    """Prévient la personne et la bannit automatiquement au 3e avertissement."""
    user = warning.user
    count = active_warning_count(user)
    if count >= MAX_WARNINGS:
        ban_user(user, f"{MAX_WARNINGS} avertissements reçus. Dernier motif : {warning.reason}",
                 by=warning.issued_by, automatic=True)
        return
    text = f"Avertissement {count}/{MAX_WARNINGS} de Lantante Technologie. Motif : {warning.reason}"
    if count == MAX_WARNINGS - 1:
        text += f"\n\nAttention : au prochain avertissement, votre compte sera suspendu."
    else:
        text += f"\n\nÀ {MAX_WARNINGS} avertissements, votre compte est suspendu."
    notify(user, text, '/emploi/mon-espace/')


def warn_user(user, reason, by=None):
    from .models import ModerationWarning
    if not can_sanction(user):
        raise ValueError("Un membre de l'équipe ne peut pas être sanctionné ici.")
    warning = ModerationWarning.objects.create(user=user, reason=reason, issued_by=by)
    apply_warning(warning)
    return warning


def ban_user(user, reason, by=None, automatic=False):
    """Bloque le compte (connexion impossible), masque ses contenus et prévient la personne par e-mail."""
    from django.utils import timezone
    from .models import AccountBan, FeedPost, JobOffer
    if not can_sanction(user):
        raise ValueError("Un membre de l'équipe ne peut pas être banni ici.")
    ban, _ = AccountBan.objects.update_or_create(
        user=user, defaults={'reason': reason, 'automatic': automatic, 'banned_by': by,
                             'banned_at': timezone.now(), 'lifted_at': None})
    if user.is_active:
        user.is_active = False
        user.save(update_fields=['is_active'])
    # Ses contenus disparaissent du site (rien n'est supprimé).
    FeedPost.objects.filter(author=user).update(is_hidden=True)
    candidate = getattr(user, 'candidate_profile', None)
    if candidate:
        candidate.is_published = False
        candidate.save(update_fields=['is_published'])
    employer = getattr(user, 'employer_profile', None)
    if employer:
        employer.status = 'rejected'
        employer.decision_message = "Compte suspendu par Lantante Technologie."
        employer.save(update_fields=['status', 'decision_message'])
        JobOffer.objects.filter(employer=employer, status='published').update(status='closed')
    notify(user, "Votre compte Lantante Technologie a été suspendu."
                 f"\n\nMotif : {reason}"
                 "\n\nSi vous pensez qu'il s'agit d'une erreur, répondez à cet e-mail pour contester la décision.",
           '/users/connexion/')
    return ban


def unban_user(user, by=None):
    from django.utils import timezone
    ban = getattr(user, 'ban', None)
    user.is_active = True
    user.save(update_fields=['is_active'])
    user.moderation_warnings.filter(is_active=True).update(is_active=False)  # le compteur repart de zéro
    if ban and ban.lifted_at is None:
        ban.lifted_at = timezone.now()
        ban.save(update_fields=['lifted_at'])
    notify(user, "Votre compte Lantante Technologie est de nouveau actif. Merci de respecter les règles de la plateforme.",
           '/emploi/mon-espace/')


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


def staff_users():
    """Tous les comptes de l'équipe Lantante actifs."""
    User = get_user_model()
    return User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True))


def account_kind(user):
    """'candidate', 'employer', 'member' (particulier), 'undefined' (pas encore choisi) ou 'anonymous'.
    Trois espaces séparés : jamais deux à la fois."""
    if not user.is_authenticated:
        return 'anonymous'
    kind = getattr(user, 'account_type', '')
    if kind in ('candidate', 'employer', 'member'):
        return kind
    if hasattr(user, 'employer_profile') and not hasattr(user, 'candidate_profile'):
        return 'employer'
    if hasattr(user, 'candidate_profile'):
        return 'candidate'
    return 'undefined'


def is_staff(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def can_browse_candidates(user):
    """Les profils des candidats sont masqués : seul Lantante parcourt la liste. Une entreprise ne voit que ceux
    qui ont postulé à ses offres."""
    return user.is_authenticated and is_staff(user)


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
            results.append({'candidate': cand, 'score': score, 'reasons': ", ".join(reasons),
                            'boosted': cand.is_boosted})
    # Le boost est un simple départage à score égal : il ne fait jamais passer devant un meilleur profil.
    results.sort(key=lambda r: (r['score'], r['boosted']), reverse=True)
    return results[:limit]
