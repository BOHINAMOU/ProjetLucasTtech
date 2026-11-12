from django.contrib import admin
from django.utils.html import format_html

from .models import Contest, ContestCategory, ContestSession, Correction, ExamPaper, Specialty


@admin.register(ContestCategory)
class ContestCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order')
    list_editable = ('order',)
    prepopulated_fields = {'slug': ('name',)}


class SessionInline(admin.TabularInline):
    model = ContestSession
    extra = 1
    fields = ('year', 'is_published')
    show_change_link = True


class SpecialtyInline(admin.TabularInline):
    model = Specialty
    extra = 0


@admin.register(Contest)
class ContestAdmin(admin.ModelAdmin):
    list_display = ('acronym', 'name', 'category', 'country', 'is_published', 'n_sessions')
    list_filter = ('is_published', 'category', 'country')
    list_editable = ('is_published',)
    search_fields = ('acronym', 'name')
    prepopulated_fields = {'slug': ('acronym',)}
    inlines = [SessionInline, SpecialtyInline]

    @admin.display(description="Années")
    def n_sessions(self, obj):
        return obj.sessions.count()


class PaperInline(admin.StackedInline):
    model = ExamPaper
    extra = 1
    fields = (('title', 'subject'), ('duration', 'coefficient', 'specialty'), 'file', ('is_free', 'is_published', 'order'))
    show_change_link = True


@admin.register(ContestSession)
class ContestSessionAdmin(admin.ModelAdmin):
    list_display = ('contest', 'year', 'is_published', 'n_papers')
    list_filter = ('is_published', 'contest__category', 'contest')
    search_fields = ('contest__acronym', 'contest__name')
    autocomplete_fields = ('contest',)
    inlines = [PaperInline]

    @admin.display(description="Épreuves")
    def n_papers(self, obj):
        return obj.papers.count()


class CorrectionInline(admin.TabularInline):
    model = Correction
    extra = 1
    fields = ('kind', 'author', 'file', 'is_published')


@admin.register(ExamPaper)
class ExamPaperAdmin(admin.ModelAdmin):
    list_display = ('title', 'session', 'subject', 'is_free', 'is_published', 'n_corrections', 'preview')
    list_filter = ('is_free', 'is_published', 'session__contest', 'session__year')
    list_editable = ('is_free', 'is_published')
    search_fields = ('title', 'subject', 'session__contest__acronym', 'session__contest__name')
    autocomplete_fields = ('session',)
    inlines = [CorrectionInline]

    @admin.display(description="Corrigés")
    def n_corrections(self, obj):
        return obj.corrections.count()

    @admin.display(description="Lecteur")
    def preview(self, obj):
        return format_html('<a href="/concours/lire/sujet/{}/" target="_blank">Ouvrir</a>', obj.pk)


@admin.register(Correction)
class CorrectionAdmin(admin.ModelAdmin):
    list_display = ('paper', 'kind', 'author', 'is_published', 'created_at')
    list_filter = ('kind', 'is_published', 'paper__session__contest')
    search_fields = ('paper__title', 'paper__session__contest__acronym')
    autocomplete_fields = ('paper',)


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ('name', 'contest')
    search_fields = ('name', 'contest__acronym')
