from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User

    list_display = ("email", "is_staff", "is_active", "is_premium")
    list_filter = ("is_staff", "is_active", "is_premium")
    ordering = ("email",)
    search_fields = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profil", {
            "fields": ("phone", "avatar", "date_of_birth", "country", "city")
        }),
        ("Permissions", {
            "fields": ("is_staff", "is_active", "is_superuser", "is_verified", "is_premium")
        }),
        ("Dates système", {
            "fields": ("last_login",)
        }),
    )

    readonly_fields = ("last_login",)  # important

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "is_staff", "is_active"),
        }),
    )