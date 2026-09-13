from django import forms
from django.contrib import admin
from .models import Formation


class FormationAdminForm(forms.ModelForm):
    class Meta:
        model = Formation
        fields = '__all__'
        widgets = {
            'what_you_learn': forms.Textarea(attrs={
                'rows': 8,
                'placeholder': 'Un point par ligne, par exemple :\nStructurer une campagne Google Ads\nCibler efficacement sur Facebook et Instagram\nMaîtriser son budget et son coût par résultat',
            }),
            'description': forms.Textarea(attrs={'rows': 5}),
        }


@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    form = FormationAdminForm
    list_display = ('title', 'level', 'price', 'old_price', 'is_featured', 'author', 'is_published', 'created_at')
    list_filter = ('is_published', 'is_featured', 'level', 'created_at')
    search_fields = ('title', 'description')
    ordering = ('-created_at',)

    fieldsets = (
        ('Informations principales', {
            'fields': ('title', 'author', 'image', 'description')
        }),
        ('Contenu pédagogique', {
            'fields': ('what_you_learn',),
            'description': "Un point par ligne — chaque ligne devient une case à cocher sur la fiche de la formation.",
        }),
        ('Prix et promotion', {
            'fields': ('price', 'old_price'),
            'description': "Laissez « Ancien prix » vide s'il n'y a pas de promotion. S'il est renseigné et supérieur au prix, le badge de réduction s'affiche automatiquement.",
        }),
        ('Détails affichés', {
            'fields': ('level', 'duration', 'students_count'),
        }),
        ('Publication', {
            'fields': ('is_published', 'is_featured'),
        }),
    )
