from django.db import models
from .countries import COUNTRIES


# ─────────────────────────────
# 🖼️ SLIDES DU CARROUSEL D'ACCUEIL
# ─────────────────────────────
class HeroSlide(models.Model):
    tag      = models.CharField(max_length=80, verbose_name="Étiquette", help_text="Ex : Formations, E-Commerce")
    title    = models.CharField(
        max_length=255, verbose_name="Titre",
        help_text="Vous pouvez mettre un mot en évidence (doré) en l'entourant de <em>...</em>"
    )
    subtitle = models.TextField(blank=True, verbose_name="Sous-titre")
    image    = models.ImageField(upload_to='hero_slides/', verbose_name="Image de fond")
    link_url  = models.CharField(max_length=255, verbose_name="Lien", help_text="Ex : /boutique/ ou https://...")
    link_text = models.CharField(max_length=80, default="En savoir plus", verbose_name="Texte du bouton")
    order     = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Slide du carrousel"
        verbose_name_plural = "Slides du carrousel"

    def __str__(self):
        return self.tag or self.title


# ─────────────────────────────
# 📰 BARRE D'ACTUALITÉS DÉFILANTE
# ─────────────────────────────
class NewsTickerItem(models.Model):
    label    = models.CharField(max_length=40, verbose_name="Étiquette", help_text="Ex : Nouveau, Boutique, Article")
    message  = models.CharField(max_length=150, verbose_name="Message")
    link_url = models.CharField(max_length=255, verbose_name="Lien", help_text="Ex : /formations/ ou https://...")
    order    = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Actualité (bandeau)"
        verbose_name_plural = "Actualités (bandeau)"

    def __str__(self):
        return f"{self.label} — {self.message}"


# ─────────────────────────────
# 📂 CATÉGORIE DE PARTENAIRE
# ─────────────────────────────
class PartnerCategory(models.Model):
    name  = models.CharField(max_length=100, verbose_name="Nom")
    slug  = models.SlugField(unique=True)
    icon  = models.CharField(max_length=60, blank=True, help_text="Classe Font Awesome ex: fa-handshake")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name        = "Catégorie de partenaire"
        verbose_name_plural = "Catégories de partenaires"

    def __str__(self):
        return self.name


class Partner(models.Model):
    name        = models.CharField(max_length=100, verbose_name="Nom")
    category    = models.ForeignKey(
        PartnerCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='partners', verbose_name="Catégorie"
    )
    logo        = models.ImageField(upload_to='partners/', verbose_name="Logo")
    country     = models.CharField(max_length=100, blank=True, verbose_name="Pays / Localisation",
                                   help_text="Ex : Togo, International, Côte d'Ivoire")
    domain      = models.CharField(max_length=200, blank=True, verbose_name="Domaine d'intervention",
                                   help_text="Ex : Financement de projets numériques, Éducation")
    description = models.TextField(blank=True, verbose_name="Description")
    achievements = models.TextField(blank=True, verbose_name="Réalisations",
                                    help_text="Ce que vous avez accompli ensemble avec ce partenaire.")
    website     = models.URLField(blank=True, null=True, verbose_name="Site web")
    email       = models.EmailField(blank=True, verbose_name="Email de contact")
    phone       = models.CharField(max_length=30, blank=True, verbose_name="Téléphone")
    whatsapp    = models.CharField(max_length=30, blank=True, verbose_name="WhatsApp",
                                   help_text="Numéro complet ex : 22890000000")
    is_active   = models.BooleanField(default=True, verbose_name="Actif")
    order       = models.PositiveIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Recadre automatiquement les marges blanches/transparentes autour
        # du logo à l'envoi (un logo carré perdu au milieu d'un grand
        # rectangle blanc paraît minuscule une fois affiché dans une carte,
        # quelle que soit la mise en page) — ne s'exécute que sur un nouvel
        # envoi, pas à chaque sauvegarde du partenaire.
        if self.logo and not self.logo._committed:
            try:
                from PIL import Image, ImageChops
                import io
                from django.core.files.base import ContentFile

                self.logo.file.seek(0)
                img = Image.open(self.logo.file)
                img.load()
                img = img.convert('RGBA')
                bg = Image.new('RGBA', img.size, img.getpixel((0, 0)))
                diff = ImageChops.difference(img, bg).convert('L')
                # Seuil de tolérance : ignore le bruit JPEG / les légers
                # dégradés du fond pour ne détecter que le vrai contenu.
                diff = diff.point(lambda x: 255 if x > 30 else 0)
                bbox = diff.getbbox()
                if bbox and bbox != (0, 0, img.width, img.height):
                    margin = 6
                    l, t, r, b = bbox
                    l, t = max(0, l - margin), max(0, t - margin)
                    r, b = min(img.width, r + margin), min(img.height, b + margin)
                    img = img.crop((l, t, r, b))
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    self.logo = ContentFile(buf.getvalue(), name=self.logo.name)
            except Exception:
                pass
        super().save(*args, **kwargs)


# ─────────────────────────────
# 🤝 CANDIDATURE « DEVENIR PARTENAIRE »
# ─────────────────────────────
class PartnerApplication(models.Model):
    STATUS_CHOICES = [
        ('pending',  'En attente'),
        ('approved', 'Acceptée — publiée'),
        ('rejected', 'Rejetée'),
    ]

    full_name    = models.CharField(max_length=150, verbose_name="Nom complet")
    email        = models.EmailField(verbose_name="Email")
    whatsapp     = models.CharField(max_length=30, verbose_name="Numéro WhatsApp",
                                    help_text="Numéro complet, ex : 22890000000")
    country      = models.CharField(max_length=100, choices=[(c, c) for c in COUNTRIES], verbose_name="Pays")
    phone_code   = models.CharField(max_length=6, default='+228', verbose_name="Indicatif")
    phone_number = models.CharField(max_length=30, verbose_name="Téléphone")
    logo         = models.ImageField(upload_to='partner_applications/', verbose_name="Logo")
    description  = models.TextField(verbose_name="Présentation / description")

    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name="Statut")
    admin_note   = models.TextField(blank=True, verbose_name="Note interne")
    published_partner = models.ForeignKey(
        Partner, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='application', verbose_name="Partenaire publié"
    )
    created_at   = models.DateTimeField(auto_now_add=True)
    reviewed_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = "Candidature de partenariat"
        verbose_name_plural = "Candidatures de partenariat"

    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"

    @property
    def full_phone(self):
        return f"{self.phone_code} {self.phone_number}".strip()


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
