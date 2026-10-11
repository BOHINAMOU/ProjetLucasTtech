"""Actions métier partagées par le site web et l'API mobile : une seule règle, deux façons de l'utiliser."""
from django.utils import timezone

from .models import Appointment, Application, AvailabilitySlot
from .services import notify, notify_application_status, notify_staff

DECISIONS = {'shortlist': 'shortlisted', 'accept': 'hired', 'refuse': 'refused'}


def apply_to_offer(profile, offer, text, internship_duration='', available_from=None):
    """Le candidat postule : tout son dossier part (CV du profil, lettre, infos de stage). Retourne (candidature, créée ?)."""
    application, created = Application.objects.get_or_create(
        candidate=profile, offer=offer,
        defaults={'origin': 'candidate', 'cover_letter': text, 'message': '',
                  'internship_duration': internship_duration, 'available_from': available_from},
    )
    if created:
        notify_staff(f"Nouvelle candidature : {profile.name} → {offer.title}",
                     f"/lantanteAdminTech/Emploi/application/{application.pk}/change/")
        if offer.employer_id:
            # La candidature arrive directement chez l'entreprise : elle la traite elle-même (Lantante peut la suivre).
            application.shared_with_employer = True
            application.shared_at = timezone.now()
            application.save(update_fields=['shared_with_employer', 'shared_at'])
            notify(offer.employer.user,
                   f"Nouvelle candidature de {profile.name} pour « {offer.title} ». Consultez-la et répondez-lui.",
                   "/emploi/candidatures-recues/")
    return application, created


def decide_application(application, action, message=''):
    """L'entreprise présélectionne, accepte ou refuse : le candidat est prévenu (site, e-mail, notification mobile)."""
    application.status = DECISIONS[action]
    application.status_message = message.strip()[:1000] if (action != 'accept' or message) else ''
    application.save()
    notify_application_status(application)
    return application


def schedule_interview(application, when, place='', notes=''):
    """L'entreprise fixe l'entretien (date déjà validée, à venir) : rendez-vous créé, candidat prévenu."""
    target = application.offer or application.request
    place = place.strip()[:200]
    appointment = Appointment.objects.create(
        application=application, candidate=application.candidate, employer=application.employer,
        title=f"Entretien — {target}", scheduled_at=when, place=place, notes=notes.strip())
    application.status = 'interview'
    application.save(update_fields=['status', 'updated_at'])
    local = timezone.localtime(when).strftime('%d/%m/%Y à %H:%M')
    notify(application.candidate.user,
           f"{application.employer.company_name} vous propose un entretien pour « {target} » le {local}."
           + (f" Lieu / lien : {place}." if place else "") + " Confirmez votre présence dans « Rendez-vous ».",
           '/emploi/rendez-vous/')
    return appointment


def submit_availability(application, starts, note=''):
    """Le candidat présélectionné propose ses créneaux ; l'entreprise (ou Lantante pour ses offres) est prévenue."""
    application.slots.all().delete()
    slots = [AvailabilitySlot.objects.create(application=application, start=when, note=note) for when in starts]
    target = application.offer or application.request
    when_txt = ", ".join(timezone.localtime(s.start).strftime('%d/%m %H:%M') for s in slots)
    text = f"{application.candidate.name} est disponible pour l'entretien « {target} » : {when_txt}"
    employer = application.employer
    if employer and application.shared_with_employer:
        notify(employer.user, text, "/emploi/candidatures-recues/")  # c'est l'entreprise qui fixe l'entretien
    else:
        notify_staff(text, f"/lantanteAdminTech/Emploi/application/{application.pk}/change/")
    return slots
