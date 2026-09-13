from django.contrib import admin
from .models import Partner, Project, TeamMember

admin.site.register(Partner)


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