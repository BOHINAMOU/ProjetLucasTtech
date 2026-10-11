"""Rapprochement automatique : quand une offre est publiée, l'équipe est alertée des demandes spontanées qui
correspondent et les candidats avec un boost Plus / Premium sont prévenus.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import JobOffer
from .services import notify, notify_staff, score_candidate


@receiver(pre_save, sender=JobOffer)
def _remember_status(sender, instance, **kwargs):
    old = JobOffer.objects.filter(pk=instance.pk).values_list('status', flat=True).first() if instance.pk else None
    instance._previous_status = old


@receiver(post_save, sender=JobOffer)
def _offer_published(sender, instance, created, **kwargs):
    if instance.status != 'published' or getattr(instance, '_previous_status', None) == 'published':
        return
    from . import spontaneous as spont
    matches = spont.match_requests_for_offer(instance)
    if matches:
        names = ", ".join(m['request'].candidate.name for m in matches[:3])
        notify_staff(f"{len(matches)} demande(s) spontanée(s) correspondent à la nouvelle offre « {instance.title} » ({names}…)",
                     f"/lantanteAdminTech/Emploi/joboffer/{instance.pk}/change/")
    # Alerte aux candidats avec un boost de 30 jours ou plus (visibilité renforcée), si l'offre leur correspond vraiment.
    from .models import BoostOrder
    from django.utils import timezone
    skill_ids = list(instance.skills.values_list('id', flat=True))
    boosts = BoostOrder.objects.filter(application__isnull=True, status='active', expires_at__gt=timezone.now(),
                                       plan__duration_days__gte=30).select_related('candidate__user')
    for boost in boosts:
        cand = boost.candidate
        if not cand.is_published or not cand.available:
            continue
        score, reasons = score_candidate(cand, instance.domain, skill_ids, instance.city)
        if score >= 40 and reasons != ["même ville"]:
            notify(cand.user, f"Une offre peut vous correspondre : « {instance.title} » ({instance.company_name}).",
                   instance.get_absolute_url())
