from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Partner, PartnerCategory, PartnerApplication, Project, TeamMember, HeroSlide, NewsTickerItem, MAX_UPLOAD_SIZE_MB
from .countries import COUNTRIES


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
    return render(request, 'core/partner_detail.html', {
        'partner': partner,
        'related': related,
    })


# ──────────────────────────────────────────
# 🤝 Devenir partenaire (candidature)
# ──────────────────────────────────────────
def partner_apply(request):
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


def projects_page(request):
    projects = Project.objects.all()

    clients = {p.client.strip() for p in projects if p.client and p.client.strip()}
    techs = set()
    for p in projects:
        techs.update(p.get_technologies())

    return render(request, 'core/projects.html', {
        'projects': projects,
        'slides': projects.exclude(image=''),
        'client_count': len(clients),
        'tech_count': len(techs),
    })


def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    related = Project.objects.exclude(pk=project.pk)[:3]
    return render(request, 'core/project_detail.html', {
        'project': project,
        'related': related,
    })


def team_page(request):
    members = TeamMember.objects.all()
    founder = members.filter(is_founder=True).first()
    return render(request, 'core/team.html', {
        'founder': founder,
        'members': members.exclude(pk=founder.pk) if founder else members,
    })


def team_member_detail(request, pk):
    member = get_object_or_404(TeamMember, pk=pk)
    return render(request, 'core/team_member_detail.html', {'member': member})
