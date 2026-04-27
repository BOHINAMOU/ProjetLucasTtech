from django.contrib import admin
from django.utils.html import format_html
from .models import PublicationCategory, Publication, PublicationImage


# ─────────────────────────────
# Images inline
# ─────────────────────────────
class PublicationImageInline(admin.TabularInline):
    model  = PublicationImage
    extra  = 3
    fields = ['image', 'caption', 'order']


# ─────────────────────────────
# Catégorie
# ─────────────────────────────
@admin.register(PublicationCategory)
class PublicationCategoryAdmin(admin.ModelAdmin):
    list_display        = ['name', 'icon', 'order']
    prepopulated_fields = {'slug': ('name',)}
    ordering            = ['order', 'name']


# ─────────────────────────────
# Publication
# ─────────────────────────────
@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display   = ['title', 'author', 'category', 'is_published', 'is_featured', 'views_count', 'created_at']
    list_filter    = ['is_published', 'is_featured', 'category']
    list_editable  = ['is_published', 'is_featured']
    search_fields  = ['title', 'content']
    prepopulated_fields = {'slug': ('title',)}
    inlines        = [PublicationImageInline]

    # ── Utilise CKEditor si disponible, sinon Textarea large ──
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'content':
            try:
                from ckeditor.widgets import CKEditorWidget
                kwargs['widget'] = CKEditorWidget(config_name='default')
            except ImportError:
                from django.forms import Textarea
                kwargs['widget'] = Textarea(attrs={'rows': 30, 'style': 'width:100%;font-size:14px;'})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(author=request.user)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" style="height:50px;border-radius:6px;">', obj.cover_image.url)
        return "—"
    cover_preview.short_description = "Couverture"

    fieldsets = (
        ('Informations principales', {
            'fields': ('title', 'slug', 'category', 'author')
        }),
        ('Médias de couverture', {
            'fields': ('cover_image', 'cover_video'),
            'classes': ('collapse',),
        }),
        ('Contenu', {
            'fields': ('content',),
        }),
        ('Publication', {
            'fields': ('is_published', 'is_featured'),
        }),
    )