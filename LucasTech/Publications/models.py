from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify


# ─────────────────────────────
# 📂 CATÉGORIE
# ─────────────────────────────
class PublicationCategory(models.Model):
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon        = models.CharField(max_length=60, blank=True, help_text="Classe Font Awesome ex: fa-heartbeat")
    slug        = models.SlugField(unique=True)
    order       = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name        = 'Catégorie'
        verbose_name_plural = 'Catégories'

    def __str__(self):
        return self.name


# ─────────────────────────────
# 📰 PUBLICATION
# ─────────────────────────────
class Publication(models.Model):
    TYPE_CHOICES = [
        ('article',   'Article / Actualité'),
        ('evenement', 'Événement (avec inscription possible)'),
    ]

    author      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='publications', verbose_name="Auteur"
    )
    category    = models.ForeignKey(
        PublicationCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='publications'
    )
    title       = models.CharField(max_length=255, verbose_name="Titre")
    slug        = models.SlugField(unique=True, blank=True, max_length=300)
    content     = models.TextField(verbose_name="Contenu (HTML)")  # CKEditor injecte ici
    cover_image = models.ImageField(upload_to='publications/covers/', blank=True, null=True,
                                    verbose_name="Image de couverture")
    cover_video = models.FileField(upload_to='publications/videos/', blank=True, null=True,
                                   verbose_name="Vidéo de couverture")
    is_published = models.BooleanField(default=False, verbose_name="Publié")
    is_featured  = models.BooleanField(default=False, verbose_name="À la une")
    views_count  = models.PositiveIntegerField(default=0, editable=False)

    # ── Événement (optionnel) ──
    publication_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='article',
                                        verbose_name="Type de publication")
    event_date        = models.DateTimeField(blank=True, null=True, verbose_name="Date de l'événement")
    event_location     = models.CharField(max_length=200, blank=True, verbose_name="Lieu de l'événement")
    registration_open  = models.BooleanField(default=True,
                                             verbose_name="Formulaire d'inscription activé",
                                             help_text="Décochez si cet événement ne propose pas d'inscription "
                                                        "(ex : simple annonce) — le bouton d'inscription n'apparaîtra pas.")
    registration_deadline = models.DateTimeField(
        blank=True, null=True, verbose_name="Date limite d'inscription",
        help_text="Passé cette date, le formulaire d'inscription n'est plus accessible "
                   "(laisser vide pour ne pas fixer de limite).",
    )

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'Publication'
        verbose_name_plural = 'Publications'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug = base
            n = 1
            while Publication.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_reading_time(self):
        """Estime le temps de lecture (200 mots/min)"""
        import re
        text = re.sub(r'<[^>]+>', '', self.content)
        words = len(text.split())
        minutes = max(1, round(words / 200))
        return minutes

    @property
    def is_event(self):
        return self.publication_type == 'evenement'

    @property
    def registration_is_open(self):
        """Inscription réellement disponible : activée ET (pas de date
        limite, ou date limite pas encore passée)."""
        if not self.registration_open:
            return False
        if self.registration_deadline and timezone.now() > self.registration_deadline:
            return False
        return True


# ─────────────────────────────
# 🖼️ IMAGES SUPPLÉMENTAIRES
# ─────────────────────────────
class PublicationImage(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='images')
    image       = models.ImageField(upload_to='publications/gallery/')
    caption     = models.CharField(max_length=200, blank=True, verbose_name="Légende")
    order       = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Image de {self.publication.title}"


# ─────────────────────────────
# 🎬 VIDÉOS SUPPLÉMENTAIRES
# ─────────────────────────────
class PublicationVideo(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE, related_name='videos')
    video       = models.FileField(upload_to='publications/gallery-videos/')
    caption     = models.CharField(max_length=200, blank=True, verbose_name="Légende")
    order       = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Vidéo de {self.publication.title}"


# ─────────────────────────────
# 📝 INSCRIPTION À UN ÉVÉNEMENT
# ─────────────────────────────
class EventRegistration(models.Model):
    publication  = models.ForeignKey(
        Publication, on_delete=models.CASCADE, related_name='registrations',
        limit_choices_to={'publication_type': 'evenement'},
    )
    first_name   = models.CharField(max_length=100, verbose_name="Prénom")
    last_name    = models.CharField(max_length=100, verbose_name="Nom")
    email        = models.EmailField(verbose_name="Email")
    phone_code   = models.CharField(max_length=6, default='+228', verbose_name="Indicatif")
    phone_number = models.CharField(max_length=30, default='', verbose_name="Numéro WhatsApp")
    country      = models.CharField(max_length=100, blank=True, verbose_name="Pays")
    city         = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = "Inscription à un événement"
        verbose_name_plural = "Inscriptions aux événements"

    def __str__(self):
        return f"{self.first_name} {self.last_name} → {self.publication.title}"

    @property
    def full_phone(self):
        return f"{self.phone_code} {self.phone_number}".strip()