from django.shortcuts import render
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
    return render(request, 'core/projects.html', {
        'projects': Project.objects.all(),
    })


def team_page(request):
    members = TeamMember.objects.all()
    founder = members.filter(is_founder=True).first()
    return render(request, 'core/team.html', {
        'founder': founder,
        'members': members.exclude(pk=founder.pk) if founder else members,
    })
