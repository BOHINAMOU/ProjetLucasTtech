from django.contrib import admin
from .models import Partner, Project, TeamMember, HeroSlide, NewsTickerItem

admin.site.register(Partner)


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('tag', 'title', 'link_url', 'order', 'is_active')
    list_editable = ('order', 'is_active')


@admin.register(NewsTickerItem)
class NewsTickerItemAdmin(admin.ModelAdmin):
    list_display = ('label', 'message', 'link_url', 'order', 'is_active')
    list_editable = ('order', 'is_active')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'client', 'year', 'order')
    list_editable = ('order',)
    search_fields = ('title', 'client', 'description')


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'is_founder', 'order')
    list_editable = ('order',)
    list_filter = ('is_founder',)
    search_fields = ('name', 'role')