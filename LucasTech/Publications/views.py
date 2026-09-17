# Create your views here.
import re

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings

from core.countries import COUNTRIES, DIAL_CODE_CHOICES
from .models import Publication, PublicationCategory, EventRegistration

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


# ─────────────────────────────
# 📰 LISTE DES PUBLICATIONS
# ─────────────────────────────
CAT_COLORS = ['c-1', 'c-2', 'c-3', 'c-4', 'c-5']


def publications(request):
    categories    = PublicationCategory.objects.all()
    category_slug = request.GET.get('category', '').strip()
    search_query  = request.GET.get('q', '').strip()
    nav_categories = [
        (cat, CAT_COLORS[i % len(CAT_COLORS)]) for i, cat in enumerate(categories)
    ]

    qs = Publication.objects.filter(is_published=True).select_related('author', 'category')

    active_category = None
    if category_slug:
        active_category = PublicationCategory.objects.filter(slug=category_slug).first()
        if active_category:
            qs = qs.filter(category=active_category)

    if search_query:
        words = search_query.split()
        query = Q()
        for word in words:
            query &= (Q(title__icontains=word) | Q(content__icontains=word))
        qs = qs.filter(query)

    # À la une (featured) séparés pour le hero
    featured = qs.filter(is_featured=True).first()

    return render(request, 'publications/publications.html', {
        'publications':    qs,
        'categories':      categories,
        'nav_categories':  nav_categories,
        'active_category': active_category,
        'search_query':    search_query,
        'featured':        featured,
    })


# ─────────────────────────────
# 📄 DÉTAIL PUBLICATION
# ─────────────────────────────
def publication_detail(request, slug):
    publication = get_object_or_404(Publication, slug=slug, is_published=True)

    # Incrémenter les vues
    Publication.objects.filter(pk=publication.pk).update(views_count=publication.views_count + 1)

    # Articles similaires (même catégorie) ; on complète avec les plus
    # récentes publications toutes catégories confondues si besoin, pour
    # toujours proposer jusqu'à 4 suggestions.
    base_qs = Publication.objects.filter(is_published=True).exclude(pk=publication.pk)

    related = list(base_qs.filter(category=publication.category)[:4]) if publication.category else []
    if len(related) < 4:
        exclude_ids = [publication.pk] + [p.pk for p in related]
        extra = base_qs.exclude(pk__in=exclude_ids)[:4 - len(related)]
        related += list(extra)

    return render(request, 'publications/publication_detail.html', {
        'publication': publication,
        'related':     related,
    })


# ─────────────────────────────
# 📝 INSCRIPTION À UN ÉVÉNEMENT
# ─────────────────────────────
def publication_register(request, slug):
    publication = get_object_or_404(
        Publication, slug=slug, is_published=True, publication_type='evenement'
    )

    if not publication.registration_is_open:
        messages.error(request, "Les inscriptions pour cet événement sont fermées.")
        return redirect('publications:publication_detail', slug=slug)

    if request.method == 'POST':
        first_name   = request.POST.get('first_name', '').strip()
        last_name    = request.POST.get('last_name', '').strip()
        email        = request.POST.get('email', '').strip()
        phone_code   = request.POST.get('phone_code', '+228').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        country      = request.POST.get('country', '').strip()
        city         = request.POST.get('city', '').strip()

        errors = []
        if not first_name: errors.append("Le prénom est requis.")
        if not last_name: errors.append("Le nom est requis.")
        if not email:
            errors.append("L'email est requis.")
        elif not EMAIL_RE.match(email):
            errors.append("L'adresse email n'est pas valide.")
        if not phone_number: errors.append("Le numéro WhatsApp est requis.")
        if not country: errors.append("Le pays est requis.")
        if not city: errors.append("La ville est requise.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'publications/publication_register.html', {
                'publication': publication,
                'form_data': request.POST,
                'countries': COUNTRIES,
                'dial_codes': DIAL_CODE_CHOICES,
            })

        EventRegistration.objects.create(
            publication=publication,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_code=phone_code,
            phone_number=phone_number,
            country=country,
            city=city,
        )

        try:
            subject = f"Merci pour votre inscription — {publication.title}"
            body = (
                f"Bonjour {first_name},\n\n"
                f"Merci pour votre inscription à l'événement « {publication.title} ».\n\n"
            )
            if publication.event_date:
                body += f"Date : {publication.event_date.strftime('%d/%m/%Y à %H:%M')}\n"
            if publication.event_location:
                body += f"Lieu : {publication.event_location}\n"
            body += "\nNous vous recontacterons si des informations complémentaires sont nécessaires.\n\n"
            body += "À très bientôt,\nL'équipe Lantante Technologie"
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
        except Exception:
            pass

        return redirect('publications:publication_register_success', slug=publication.slug)

    return render(request, 'publications/publication_register.html', {
        'publication': publication,
        'countries': COUNTRIES,
        'dial_codes': DIAL_CODE_CHOICES,
    })


def publication_register_success(request, slug):
    publication = get_object_or_404(Publication, slug=slug)
    return render(request, 'publications/publication_register_success.html', {
        'publication': publication,
    })
