import csv
from django import forms
from django.contrib import admin
from django.http import HttpResponse
from .models import Formation, FormationCategory, Order, OrderItem, Registration


@admin.register(FormationCategory)
class FormationCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'order']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'name']


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
    list_display = ('title', 'category', 'formation_type', 'level', 'price', 'old_price', 'is_featured', 'author', 'is_published', 'created_at')
    list_filter = ('category', 'formation_type', 'is_published', 'is_featured', 'level', 'created_at')
    search_fields = ('title', 'description')
    ordering = ('-created_at',)
    exclude = ('author',)

    def save_model(self, request, obj, form, change):
        # L'auteur n'est jamais choisi dans le formulaire : c'est toujours
        # la personne connectée qui publie.
        if not obj.pk:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    fieldsets = (
        ('Type de formation', {
            'fields': ('formation_type',),
            'description': (
                "• Formation payante en ligne : achat via panier, le client peut ensuite nous "
                "contacter sur WhatsApp avec la liste de ses formations choisies.<br>"
                "• Inscription par formulaire : le client remplit un formulaire, reçoit un email "
                "avec le lien du groupe WhatsApp. Voir les inscriptions dans « Inscriptions » ci-dessous.<br>"
                "• Formation numérique : fichier PDF/Word/Excel téléchargeable une fois la commande "
                "marquée « Payé » dans Commandes."
            ),
        }),
        ('Informations principales', {
            'fields': ('title', 'category', 'image', 'description')
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
        ('Inscription par formulaire', {
            'fields': ('whatsapp_group_link',),
            'classes': ('collapse',),
        }),
        ('Formation numérique à télécharger', {
            'fields': ('file',),
            'classes': ('collapse',),
        }),
        ('Publication', {
            'fields': ('is_published', 'is_featured'),
        }),
    )


# ─────────────────────────────
# 📝 Inscriptions (formulaire) — export CSV/Excel
# ─────────────────────────────
@admin.action(description="Exporter la sélection en CSV (Excel)")
def export_registrations_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="inscriptions_formations.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Formation', 'Prénom', 'Nom', 'Pays', 'WhatsApp', 'Email', 'Motivation', 'Date'])
    for r in queryset.select_related('formation'):
        writer.writerow([
            r.formation.title, r.first_name, r.last_name, r.country,
            r.whatsapp_full_number, r.email, r.motivation,
            r.created_at.strftime('%d/%m/%Y %H:%M'),
        ])
    return response


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'formation', 'country', 'whatsapp_full_number', 'email', 'created_at')
    list_filter = ('formation', 'country', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'whatsapp_number')
    actions = [export_registrations_csv]

    def whatsapp_full_number(self, obj):
        return obj.whatsapp_full_number
    whatsapp_full_number.short_description = "WhatsApp"


# ─────────────────────────────
# 🧾 Commandes — confirmer le paiement manuellement
# ─────────────────────────────
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('formation', 'quantity', 'price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    list_editable = ('status',)
    search_fields = ('user__email',)
    inlines = [OrderItemInline]
