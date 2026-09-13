from django.db import models


class Partner(models.Model):
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='partners/')
    website = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name


# ─────────────────────────────
# 🚀 PROJETS RÉALISÉS
# ─────────────────────────────
class Project(models.Model):
    title       = models.CharField(max_length=200, verbose_name="Titre")
    client      = models.CharField(max_length=150, blank=True, verbose_name="Client")
    description = models.TextField(verbose_name="Description")
    image       = models.ImageField(upload_to='projects/', blank=True, null=True)
    technologies = models.CharField(
        max_length=255, blank=True,
        help_text="Séparées par des virgules, ex : Django, React, PostgreSQL"
    )
    link       = models.URLField(blank=True, verbose_name="Lien vers le projet")
    year       = models.PositiveIntegerField(blank=True, null=True, verbose_name="Année")
    order      = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-year']

    def __str__(self):
        return self.title

    def get_technologies(self):
        return [t.strip() for t in self.technologies.split(',') if t.strip()]


# ─────────────────────────────
# 👥 ÉQUIPE
# ─────────────────────────────
class TeamMember(models.Model):
    name         = models.CharField(max_length=150, verbose_name="Nom")
    role         = models.CharField(max_length=150, verbose_name="Rôle")
    bio          = models.TextField(blank=True, verbose_name="À propos")
    photo        = models.ImageField(upload_to='team/', blank=True, null=True)
    technologies = models.CharField(
        max_length=255, blank=True,
        help_text="Séparées par des virgules, ex : Python, Django, Photoshop"
    )
    phone      = models.CharField(max_length=20, blank=True)
    email      = models.EmailField(blank=True)
    facebook   = models.URLField(blank=True)
    instagram  = models.URLField(blank=True)
    linkedin   = models.URLField(blank=True)
    whatsapp   = models.CharField(max_length=20, blank=True, help_text="Numéro ex: 22890000000")
    order      = models.PositiveIntegerField(default=0)
    is_founder = models.BooleanField(default=False, verbose_name="Fondateur")

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} — {self.role}"

    def get_technologies(self):
        return [t.strip() for t in self.technologies.split(',') if t.strip()]
