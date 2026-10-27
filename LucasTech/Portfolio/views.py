from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    Profile, Skill, Project, Service, Certificate, Collaborator, Experience, Engagement, Stat, ContactMessage,
)


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '')


def _abs(request, field):
    return request.build_absolute_uri(field.url) if field else ''


def home(request):
    profile = Profile.load()
    skills = list(Skill.objects.filter(is_active=True).prefetch_related('projects'))
    projects = Project.objects.filter(is_published=True)
    certificates = list(Certificate.objects.filter(is_active=True))

    groups = []
    for code, label in Skill.CATEGORIES:
        items = [s for s in skills if s.category == code]
        if items:
            groups.append({'label': label, 'skills': items})

    skills_data = [{
        'id': s.pk, 'name': s.name, 'category': s.get_category_display(), 'level': s.get_level_display() if s.level else '',
        'icon': s.icon_class, 'logo': s.logo.url if s.logo else '',
        'description': s.description, 'usage': s.usage,
        'projects': [{'title': p.title, 'url': f"/bohinamou/projets/{p.slug}/"} for p in s.projects.all() if p.is_published],
    } for s in skills]
    certificates_data = [{
        'id': c.pk, 'title': c.title, 'kind': c.get_kind_display(), 'organization': c.organization,
        'date': c.date.strftime('%d/%m/%Y') if c.date else '', 'image': c.image.url if c.image else '',
        'file': c.file.url if c.file else '', 'verify': c.verify_url, 'description': c.description,
    } for c in certificates]

    return render(request, 'portfolio/home.html', {
        'profile': profile, 'groups': groups, 'skills_data': skills_data, 'certificates_data': certificates_data,
        'projects': projects, 'services': Service.objects.filter(is_active=True), 'certificates': certificates,
        'collaborators': Collaborator.objects.filter(is_active=True), 'experiences': Experience.objects.filter(is_active=True),
        'engagements': Engagement.objects.filter(is_active=True), 'stats': Stat.objects.filter(is_active=True),
        'photo_url': _abs(request, profile.photo),
    })


def project_detail(request, slug):
    project = get_object_or_404(Project, slug=slug, is_published=True)
    others = Project.objects.filter(is_published=True).exclude(pk=project.pk)[:3]
    return render(request, 'portfolio/project_detail.html', {
        'profile': Profile.load(), 'project': project, 'others': others,
        'image_url': _abs(request, project.image),
    })


def collaborator_detail(request, pk):
    person = get_object_or_404(Collaborator, pk=pk, is_active=True)
    others = Collaborator.objects.filter(is_active=True).exclude(pk=pk)[:4]
    return render(request, 'portfolio/collaborator_detail.html', {
        'profile': Profile.load(), 'person': person, 'others': others,
        'image_url': _abs(request, person.photo),
    })


@require_POST
def contact(request):
    back = redirect('portfolio:home')
    back['Location'] += '#contact'
    if request.POST.get('website'):  # champ piège pour les robots
        return back
    name = request.POST.get('name', '').strip()[:100]
    contact_info = request.POST.get('contact', '').strip()[:150]
    text = request.POST.get('message', '').strip()[:2000]
    if not (name and contact_info and text):
        messages.error(request, "Indiquez votre nom, un moyen de vous répondre (e-mail ou téléphone) et votre message.")
        return back
    key = f"pf-contact-{_client_ip(request)}"
    sent = cache.get(key, 0)
    if sent >= 3:
        messages.error(request, "Trop de messages en peu de temps. Réessayez dans un moment.")
        return back
    cache.set(key, sent + 1, 3600)
    msg = ContactMessage.objects.create(name=name, contact=contact_info, message=text)
    try:  # l'équipe est prévenue sur le site, par e-mail et sur l'application
        from Emploi.services import notify_staff
        notify_staff(f"Portfolio — message de {name} : {text[:120]}",
                     f"/lantanteAdminTech/Portfolio/contactmessage/{msg.pk}/change/")
    except Exception:
        pass
    messages.success(request, "Merci ! Votre message a bien été envoyé.")
    return back
