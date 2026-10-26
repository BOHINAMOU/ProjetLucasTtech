from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import render, get_object_or_404, redirect
from .models import (
    Partner, PartnerCategory, PartnerApplication, MonetizationRequest, Project, TeamMember, HeroSlide, NewsTickerItem,
    MAX_UPLOAD_SIZE_MB,
)
from .countries import COUNTRIES, DIAL_CODES, DIAL_CODE_CHOICES
from .monetization import PLATFORMS, PLATFORM_CHOICES, STEPS, WHATSAPP_WAYS, clean_phone


def home(request):
    return render(request, 'core/base.html', {
        'hero_slides': HeroSlide.objects.filter(is_active=True),
        'news_items': NewsTickerItem.objects.filter(is_active=True),
    })


def privacy_policy(request):
    return render(request, 'core/privacy_policy.html')


def terms_of_service(request):
    return render(request, 'core/terms_of_service.html')


def partners(request):
    return {
        'partners': Partner.objects.all()
    }


PARTNER_CAT_COLORS = ['c-1', 'c-2', 'c-3', 'c-4', 'c-5']


def partners_page(request):
    categories    = PartnerCategory.objects.all()
    category_slug = request.GET.get('category', '').strip()

    qs = Partner.objects.filter(is_active=True).select_related('category')

    active_category = None
    if category_slug:
        active_category = PartnerCategory.objects.filter(slug=category_slug).first()
        if active_category:
            qs = qs.filter(category=active_category)

    nav_categories = [
        (cat, PARTNER_CAT_COLORS[i % len(PARTNER_CAT_COLORS)]) for i, cat in enumerate(categories)
    ]

    countries = {p.country.strip() for p in qs if p.country and p.country.strip()}

    return render(request, 'core/partners.html', {
        'partners':        qs,
        'slides':          qs.exclude(logo=''),
        'categories':      categories,
        'nav_categories':  nav_categories,
        'active_category': active_category,
        'country_count':   len(countries),
        'category_count':  categories.count(),
    })


def partner_detail(request, pk):
    partner = get_object_or_404(Partner, pk=pk, is_active=True)
    related = Partner.objects.filter(is_active=True, category=partner.category).exclude(pk=partner.pk)[:3] \
        if partner.category else Partner.objects.none()
    # Si le partenaire a un compte entreprise accepté sur Emploi : ses publications et produits.
    employer = getattr(partner, 'employer', None)
    if employer is not None and not employer.is_approved:
        employer = None
    posts = []
    if employer is not None:
        from Emploi.models import FeedPost
        posts = FeedPost.objects.filter(author=employer.user, is_hidden=False)[:8]
    return render(request, 'core/partner_detail.html', {
        'partner': partner,
        'related': related,
        'partner_employer': employer,
        'partner_posts': posts,
    })


# ──────────────────────────────────────────
# 🤝 Devenir partenaire (candidature)
# ──────────────────────────────────────────
def partner_apply(request):
    from .context_processors import partner_cta
    if partner_cta(request)['hide_partner_cta']:
        messages.info(request, "Vous êtes déjà inscrit chez nous : le partenariat se discute directement avec Lantante (messagerie).")
        return redirect('core:partners')
    if request.method == 'POST':
        full_name    = request.POST.get('full_name', '').strip()
        email        = request.POST.get('email', '').strip()
        whatsapp     = request.POST.get('whatsapp', '').strip()
        country      = request.POST.get('country', '').strip()
        phone_code   = request.POST.get('phone_code', '+228').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        description  = request.POST.get('description', '').strip()
        logo         = request.FILES.get('logo')

        errors = []
        if not full_name: errors.append("Le nom complet est requis.")
        if not email: errors.append("L'email est requis.")
        if not whatsapp: errors.append("Le numéro WhatsApp est requis.")
        if not country: errors.append("Le pays est requis.")
        if not phone_number: errors.append("Le numéro de téléphone est requis.")
        if not logo:
            errors.append("Le logo est requis.")
        elif logo.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            errors.append(f"Le logo est trop volumineux (max {MAX_UPLOAD_SIZE_MB} Mo).")
        if not description: errors.append("La description est requise.")

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'core/partner_apply.html', {
                'form_data': request.POST,
                'countries': COUNTRIES,
            })

        PartnerApplication.objects.create(
            full_name=full_name,
            email=email,
            whatsapp=whatsapp,
            country=country,
            phone_code=phone_code,
            phone_number=phone_number,
            description=description,
            logo=logo,
        )
        return redirect('core:partner_apply_success')

    return render(request, 'core/partner_apply.html', {'countries': COUNTRIES})


def partner_apply_success(request):
    return render(request, 'core/partner_apply_success.html')


def projects_team_page(request):
    """Une seule page pour « Projets réalisés » et « Notre équipe » (menu : Projets & Équipe)."""
    projects = Project.objects.all()
    clients = {p.client.strip() for p in projects if p.client and p.client.strip()}
    techs = set()
    for p in projects:
        techs.update(p.get_technologies())

    members = TeamMember.objects.all()
    founder = members.filter(is_founder=True).first()
    return render(request, 'core/projects_team.html', {
        'projects': projects,
        'slides': projects.exclude(image=''),
        'client_count': len(clients),
        'tech_count': len(techs),
        'founder': founder,
        'members': members.exclude(pk=founder.pk) if founder else members,
    })


def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    related = Project.objects.exclude(pk=project.pk)[:3]
    return render(request, 'core/project_detail.html', {
        'project': project,
        'related': related,
    })


def team_member_detail(request, pk):
    member = get_object_or_404(TeamMember, pk=pk)
    return render(request, 'core/team_member_detail.html', {'member': member})


# ─────────────────────────────
# 💰 Monétisation : présentation + formulaire d'accompagnement
# ─────────────────────────────
def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '')


def _monetization_context(form_data=None):
    return {
        'platforms': PLATFORMS, 'platform_choices': PLATFORM_CHOICES, 'steps': STEPS, 'whatsapp_ways': WHATSAPP_WAYS,
        'countries': [c for c in COUNTRIES if c != 'Autre'], 'dial_codes': DIAL_CODE_CHOICES,
        'dial_by_country': DIAL_CODES, 'form_data': form_data or {},
        'selected_platforms': form_data.getlist('platforms') if form_data else [],
    }


def monetization_page(request):
    if request.method != 'POST':
        return render(request, 'core/monetization.html', _monetization_context())

    data = request.POST
    if data.get('website'):  # champ piège pour les robots : on fait semblant que tout va bien
        return redirect('core:monetization_thanks')

    first_name = data.get('first_name', '').strip()[:80]
    last_name = data.get('last_name', '').strip()[:80]
    address = data.get('address', '').strip()[:200]
    country = data.get('country', '').strip()
    phone_code = data.get('phone_code', '').strip()
    platforms = [p for p in data.getlist('platforms') if p in PLATFORM_CHOICES]
    message = data.get('message', '').strip()[:1500]

    errors = []
    if not first_name: errors.append("Le prénom est requis.")
    if not last_name: errors.append("Le nom est requis.")
    if not address: errors.append("L'adresse est requise.")
    if country not in COUNTRIES or country == 'Autre': errors.append("Choisissez votre pays dans la liste.")
    if phone_code not in {c for c, _ in DIAL_CODE_CHOICES}: errors.append("Choisissez l'indicatif de votre pays.")
    number, phone_error = clean_phone(phone_code, data.get('phone_number', ''))
    if phone_error: errors.append(phone_error)

    if not errors:
        key = f"monet-{_client_ip(request)}"
        sent = cache.get(key, 0)
        if sent >= 5:
            errors.append("Trop de demandes en peu de temps. Réessayez dans un moment ou écrivez-nous sur WhatsApp.")
        else:
            cache.set(key, sent + 1, 3600)

    if errors:
        for e in errors:
            messages.error(request, e)
        return render(request, 'core/monetization.html', _monetization_context(data))

    req = MonetizationRequest.objects.create(
        first_name=first_name, last_name=last_name, address=address, country=country,
        phone_code=phone_code, phone_number=number, platforms=', '.join(platforms), message=message,
    )
    try:  # l'équipe est prévenue sur le site, par e-mail et sur l'application
        from Emploi.services import notify_staff
        notify_staff(f"Nouvelle demande de monétisation : {req.full_name} ({req.country}), {req.full_phone}",
                     f"/lantanteAdminTech/core/monetizationrequest/{req.pk}/change/")
    except Exception:
        pass
    return redirect('core:monetization_thanks')


def monetization_thanks(request):
    return render(request, 'core/monetization_thanks.html')
