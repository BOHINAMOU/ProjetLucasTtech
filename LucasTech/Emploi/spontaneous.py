"""Demandes spontanées : vivier de talents, rapprochement avec les offres, accord du candidat avant transmission."""
from django.db.models import Q
from django.utils import timezone

from .models import Application, JobOffer, SpontaneousRequest
from .services import notify, notify_staff

# Type de demande -> contrats d'offre compatibles (None = tous)
REQUEST_CONTRACTS = {
    'job': ('cdi', 'cdd', 'freelance', 'interim'),
    'intern_academic': ('stage',),
    'intern_pro': ('stage',),
    'alternance': ('alternance',),
    'other': None,
}


def _compatible(request_type, contract):
    allowed = REQUEST_CONTRACTS.get(request_type)
    return allowed is None or contract in allowed


def open_offers():
    return JobOffer.objects.filter(status='published').filter(
        Q(deadline__isnull=True) | Q(deadline__gte=timezone.localdate())
    ).filter(Q(employer__isnull=True) | Q(employer__status='approved')).select_related('employer')


def score_request_for_offer(req, offer):
    """0-100 : domaine (40) + compétences (40) + ville (20). Contrat compatible obligatoire ; la ville seule ne suffit pas."""
    if not _compatible(req.request_type, offer.contract):
        return 0, []
    score, reasons = 0, []
    if req.domain == offer.domain:
        score += 40
        reasons.append("même domaine")
    wanted = set(offer.skills.values_list('id', flat=True))
    have = set(req.skills.values_list('id', flat=True)) | set(req.candidate.skills.values_list('id', flat=True))
    if wanted and wanted & have:
        score += round(40 * len(wanted & have) / len(wanted))
        reasons.append(f"{len(wanted & have)}/{len(wanted)} compétence(s)")
    city = (req.city or req.candidate.city or '').strip().lower()
    if city and offer.city and city == offer.city.strip().lower():
        score += 20
        reasons.append("même ville")
    if not (set(reasons) - {"même ville"}):
        return 0, []
    return score, reasons


def match_offers_for_request(req, limit=20):
    already = set(req.candidate.applications.values_list('offer_id', flat=True))
    results = []
    for offer in open_offers():
        if offer.pk in already:
            continue
        score, reasons = score_request_for_offer(req, offer)
        if score:
            results.append({'offer': offer, 'score': score, 'reasons': ", ".join(reasons)})
    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:limit]


def match_requests_for_offer(offer, limit=50):
    """Demandes spontanées en attente qui correspondent à une offre (nouvelle ou existante)."""
    results = []
    for req in SpontaneousRequest.objects.filter(status__in=('pending', 'in_progress'),
                                                 candidate__is_published=True).select_related('candidate__user'):
        score, reasons = score_request_for_offer(req, offer)
        if score >= 40:
            results.append({'request': req, 'score': score, 'reasons': ", ".join(reasons)})
    results.sort(key=lambda r: r['score'], reverse=True)
    return results[:limit]


def notify_spontaneous_status(req):
    """Prévient le candidat quand sa demande évolue (site + e-mail)."""
    extra = f"\n\n{req.status_message.strip()}" if req.status_message.strip() else ""
    label = req.get_request_type_display().lower()
    texts = {
        'in_progress': f"Votre demande spontanée ({label}) est en cours de traitement par Lantante.",
        'matched': f"Bonne nouvelle : votre demande spontanée ({label}) correspond à une opportunité. Lantante vous contacte.",
        'transmitted': f"Votre dossier (demande spontanée, {label}) a été transmis à une entreprise, avec votre accord.",
        'interview': f"Un entretien vous est proposé suite à votre demande spontanée ({label}). Consultez vos rendez-vous.",
        'closed': f"Votre demande spontanée ({label}) est clôturée.",
        'rejected': f"Votre demande spontanée ({label}) n'a pas pu être retenue pour le moment.",
    }
    text = texts.get(req.status)
    return notify(req.candidate.user, text + extra, '/emploi/demandes/') if text else None


def propose_offer_to_candidate(req, offer):
    """Lantante propose une offre à l'auteur d'une demande spontanée : transmission seulement avec son accord."""
    application, created = Application.objects.get_or_create(
        candidate=req.candidate, offer=offer,
        defaults={'origin': 'lantante', 'status': 'received', 'consent': 'pending', 'spontaneous': req})
    if created:
        if req.status in ('pending', 'in_progress'):
            req.status = 'matched'
            req.save(update_fields=['status', 'updated_at'])
        notify(req.candidate.user,
               f"Une opportunité correspond à votre demande : « {offer.title} » ({offer.company_name}). "
               "Acceptez-vous que Lantante transmette votre dossier à l'entreprise ? Répondez depuis « Mon espace ».",
               '/emploi/mon-espace/#candidatures')
    return application, created


def respond_consent(application, accept):
    """Réponse du candidat à une opportunité proposée par Lantante."""
    application.consent = 'accepted' if accept else 'declined'
    if not accept:
        application.status = 'treated'
        application.status_message = "Le candidat n'a pas souhaité donner suite."
    application.save()
    target = application.offer or application.request
    url = f"/lantanteAdminTech/Emploi/application/{application.pk}/change/"
    if accept:
        notify_staff(f"{application.candidate.name} accepte la transmission de son dossier pour « {target} ».", url)
    else:
        notify_staff(f"{application.candidate.name} refuse l'opportunité « {target} ».", url)
        spontaneous = application.spontaneous
        if spontaneous and spontaneous.status == 'matched':
            spontaneous.status = 'in_progress'
            spontaneous.save(update_fields=['status', 'updated_at'])
