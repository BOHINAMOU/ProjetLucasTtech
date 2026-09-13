from django.contrib import admin
from .models import Formation


@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    list_display = ('title', 'level', 'price', 'old_price', 'is_featured', 'author', 'is_published', 'created_at')
    list_filter = ('is_published', 'is_featured', 'level', 'created_at')
    search_fields = ('title', 'description')
    ordering = ('-created_at',)

# Register your models here.
