"""Représentations JSON des objets pour l'application mobile (dictionnaires simples, sans magie)."""
from django.utils import timezone

from ..models import CONTRACT_CHOICES, DOMAIN_CHOICES
from ..services import account_kind

CONTRACTS = dict(CONTRACT_CHOICES)
DOMAINS = dict(DOMAIN_CHOICES)


def abs_url(request, field):
    """Adresse complète d'un fichier public (logo, photo, couverture) ; None s'il n'y en a pas."""
    try:
        return request.build_absolute_uri(field.url) if field else None
    except ValueError:
        return None


def dt(value):
    return timezone.localtime(value).isoformat() if value else None


def user_payload(request, user):
    kind = account_kind(user)
    data = {
        'id': user.pk, 'email': user.email, 'first_name': user.first_name, 'last_name': user.last_name,
        'name': user.public_name, 'phone': user.phone or '', 'city': user.city or '', 'country': user.country or '',
        'avatar': abs_url(request, user.avatar), 'account_type': getattr(user, 'account_type', ''),
        'kind': kind, 'is_staff': bool(user.is_staff or user.is_superuser),
        'has_profile': hasattr(user, 'candidate_profile') or hasattr(user, 'employer_profile'),
    }
    employer = getattr(user, 'employer_profile', None)
    if employer:
        data['employer_status'] = employer.status
    return data


def skills_list(obj):
    return list(obj.skills.values_list('name', flat=True))


def company_payload(request, e, detail=False):
    data = {
        'id': e.pk, 'name': e.company_name, 'logo': abs_url(request, e.logo) or (abs_url(request, e.partner.logo) if e.partner_id else None),
        'sector': e.sector, 'sector_label': DOMAINS.get(e.sector, ''), 'city': e.city, 'verified': e.is_verified,
        'is_partner': bool(e.partner_id), 'user_id': e.user_id,
    }
    if detail:
        data.update({
            'description': e.description, 'products': e.product_list, 'website': e.website, 'whatsapp': e.whatsapp,
            'contact_email': e.contact_email, 'employees_count': e.employees_count,
        })
    return data


def offer_payload(request, o, detail=False):
    data = {
        'id': o.pk, 'slug': o.slug, 'title': o.title, 'company': o.company_name,
        'company_id': o.employer_id, 'company_logo': abs_url(request, o.employer.logo) if o.employer_id and o.employer.logo else None,
        'domain': o.domain, 'domain_label': DOMAINS.get(o.domain, ''), 'contract': o.contract,
        'contract_label': CONTRACTS.get(o.contract, ''), 'city': o.city, 'duration': o.duration,
        'salary': o.salary, 'deadline': o.deadline.isoformat() if o.deadline else None, 'featured': o.is_featured,
        'cover_image': abs_url(request, o.cover_image), 'requires_cover_letter': o.requires_cover_letter,
        'status': o.status, 'created_at': dt(o.created_at),
    }
    if detail:
        data.update({'description': o.description, 'requirements': o.requirements, 'skills': skills_list(o)})
    return data


def candidate_payload(request, c, private=False):
    data = {
        'id': c.pk, 'name': c.name, 'headline': c.headline, 'domain': c.domain, 'domain_label': DOMAINS.get(c.domain, ''),
        'skills': skills_list(c), 'city': c.city, 'bio': c.bio, 'experience_years': c.experience_years,
        'education_level': c.education_level, 'contract_wanted': c.contract_wanted_codes, 'available': c.available,
        'seeking_internship': c.seeking_internship, 'internship_duration': c.internship_duration,
        'available_from': c.available_from.isoformat() if c.available_from else None,
        'avatar': abs_url(request, c.user.avatar), 'is_published': c.is_published,
    }
    if private:  # CV, coordonnées, lettre : propriétaire ou entreprise ayant reçu la candidature
        data.update({
            'user_id': c.user_id, 'email': c.user.email, 'phone': c.phone or c.user.phone or '', 'cover_letter': c.cover_letter,
            'has_cv': bool(c.cv), 'cv_url': request.build_absolute_uri(f'/api/v1/candidates/{c.pk}/cv') if c.cv else None,
            'documents': [document_payload(request, d) for d in c.documents.all()],
        })
    return data


def document_payload(request, d):
    return {'id': d.pk, 'kind': d.kind, 'kind_label': d.get_kind_display(), 'title': d.title,
            'url': request.build_absolute_uri(f'/api/v1/documents/{d.pk}/file'), 'created_at': dt(d.created_at)}


def appointment_payload(a):
    return {
        'id': a.pk, 'title': a.title, 'scheduled_at': dt(a.scheduled_at), 'place': a.place, 'notes': a.notes,
        'status': a.status, 'status_label': a.get_status_display(), 'candidate': a.candidate.name,
        'company': a.employer.company_name if a.employer_id else None, 'application_id': a.application_id,
    }


def application_payload(request, a, for_employer=False):
    target = a.offer or a.request
    data = {
        'id': a.pk, 'status': a.status, 'status_label': a.get_status_display(), 'step': a.step_index,
        'offer': offer_payload(request, a.offer) if a.offer_id else None,
        'title': target.title if target else '', 'company': a.employer.company_name if a.employer else 'Lantante Technologie',
        'created_at': dt(a.created_at), 'cover_letter': a.cover_letter, 'status_message': a.status_message,
        'internship_duration': a.internship_duration,
        'available_from': a.available_from.isoformat() if a.available_from else None,
        'consent': a.consent, 'origin': a.origin, 'incomplete': a.missing_items,
        'slots': [{'start': dt(s.start), 'note': s.note} for s in a.slots.all()],
        'appointments': [appointment_payload(x) for x in a.appointments.all()],
    }
    if for_employer:
        data['candidate'] = candidate_payload(request, a.candidate, private=True)
    return data


def spontaneous_payload(r):
    return {
        'id': r.pk, 'request_type': r.request_type, 'request_type_label': r.get_request_type_display(),
        'domain': r.domain, 'domain_label': DOMAINS.get(r.domain, ''), 'skills': skills_list(r), 'city': r.city,
        'available_from': r.available_from.isoformat() if r.available_from else None, 'duration': r.duration,
        'message': r.message, 'status': r.status, 'status_label': r.get_status_display(),
        'status_message': r.status_message, 'withdrawn': r.withdrawn, 'can_edit': r.can_edit, 'is_open': r.is_open,
        'created_at': dt(r.created_at),
    }


def plan_payload(p):
    return {'code': p.code, 'kind': p.kind, 'name': p.name, 'description': p.description, 'advantages': p.advantages,
            'price': p.price, 'price_label': p.price_label, 'quote_only': p.quote_only, 'duration_days': p.duration_days}


def order_payload(request, o):
    return {
        'id': o.pk, 'reference': o.reference, 'plan': plan_payload(o.plan), 'status': o.status,
        'status_label': o.get_status_display(), 'step': o.step_index, 'amount': o.amount, 'amount_label': o.amount_label,
        'title': o.title, 'text': o.text, 'post_kind': o.post_kind, 'link_url': o.link_url,
        'image': abs_url(request, o.image), 'review_message': o.review_message,
        'can_pay': o.can_pay, 'can_edit': o.can_edit, 'payment_method': o.payment_method,
        'payment_reference': o.payment_reference, 'receipt_number': o.receipt_number, 'paid_at': dt(o.paid_at),
        'visible_until': dt(o.visible_until), 'created_at': dt(o.created_at),
        'offer_id': o.job_offer_id or o.boosted_offer_id,
    }


def post_payload(request, p, user=None):
    employer = p.author_employer
    return {
        'id': p.pk, 'author': p.author_label, 'author_verified': p.author_verified, 'author_company_id': employer.pk if employer else None,
        'author_logo': abs_url(request, employer.logo) if employer and employer.logo else None,
        'text': p.text, 'headline': p.headline, 'body': p.body, 'share_url': request.build_absolute_uri(f'/emploi/actualites/{p.pk}/'),
        'image': abs_url(request, p.image), 'kind': p.kind, 'sponsored': p.is_sponsored,
        'featured': bool(p.is_featured), 'likes': p.likes.count(),
        'liked': bool(user and user.is_authenticated and p.likes.filter(pk=user.pk).exists()),
        'comments': [{'id': c.pk, 'author': c.author.public_name, 'text': c.text, 'created_at': dt(c.created_at)}
                     for c in p.comments.all() if not c.is_hidden],
        'created_at': dt(p.created_at),
    }


def notification_payload(n):
    return {'id': n.pk, 'text': n.text, 'url': n.url, 'is_read': n.is_read, 'created_at': dt(n.created_at)}


def message_payload(m, me):
    return {'id': m.pk, 'author': m.author_name, 'author_role': m.author_role, 'is_automatic': m.is_automatic,
            'mine': m.sender_id == me.pk, 'body': m.body, 'created_at': dt(m.created_at)}


def conversation_payload(conv, me, with_messages=False):
    last = conv.messages.last()
    data = {
        'id': conv.pk, 'title': conv.title_for(me), 'subject': conv.subject, 'kind': conv.kind, 'status': conv.status,
        'last_message': last.body[:140] if last else '', 'updated_at': dt(conv.updated_at),
        'unread': conv.messages.exclude(sender=me).exclude(read_by=me).count(),
    }
    if conv.kind == 'support' and conv.assigned_to_id:
        data['assignee'] = {'name': conv.assigned_to.get_full_name().strip() or "Membre de l'équipe"}
    if with_messages:
        data['messages'] = [message_payload(m, me) for m in conv.messages.select_related('sender')]
    return data


def partner_payload(request, p):
    return {'id': p.pk, 'name': p.name, 'logo': abs_url(request, p.logo), 'country': p.country, 'domain': p.domain,
            'description': p.description, 'website': p.website, 'whatsapp': p.whatsapp, 'phone': p.phone, 'email': p.email}
