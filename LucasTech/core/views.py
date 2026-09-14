from django.shortcuts import render, get_object_or_404
from .models import Partner, Project, TeamMember, HeroSlide, NewsTickerItem


def home(request):
    return render(request, 'core/base.html', {
        'hero_slides': HeroSlide.objects.filter(is_active=True),
        'news_items': NewsTickerItem.objects.filter(is_active=True),
    })


def partners(request):
    return {
        'partners': Partner.objects.all()
    }


def partners_page(request):
    return render(request, 'core/partners.html', {
        'partners': Partner.objects.all(),
    })


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
