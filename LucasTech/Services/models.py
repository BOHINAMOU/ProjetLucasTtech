from django.db import models
from django.conf import settings
from django.core.mail import send_mail


# ─────────────────────────────
# 📂 CATÉGORIE DE SERVICE
# ─────────────────────────────
class ServiceCategory(models.Model):
    name        = models.CharField(max_length=100, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    icon        = models.CharField(max_length=60, blank=True, verbose_name="Icône", help_text="Classe Font Awesome ex: fa-code")
    slug        = models.SlugField(unique=True, verbose_name="Slug (URL)")
    order       = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Catégorie de service'
        verbose_name_plural = 'Catégories de service'

    def __str__(self):
        return self.name


# ─────────────────────────────
# 🛠️ SERVICE
# ─────────────────────────────
class Service(models.Model):
    admin       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='services', verbose_name="Admin responsable"
    )
    category    = models.ForeignKey(
        ServiceCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='services', verbose_name="Catégorie"
    )
    title       = models.CharField(max_length=255, verbose_name="Titre")
    description = models.TextField(verbose_name="Description")
    icon        = models.CharField(max_length=60, blank=True, verbose_name="Icône",
                                   help_text="Classe Font Awesome ex: fa-desktop (sinon, icône de la catégorie)")
    image       = models.ImageField(upload_to='services/', blank=True, null=True, verbose_name="Image")
    video       = models.FileField(upload_to='services/videos/', blank=True, null=True, verbose_name="Vidéo")
    price_from  = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Prix à partir de",
                                      help_text="Prix à partir de (optionnel)")
    whatsapp    = models.CharField(max_length=20, blank=True, verbose_name="WhatsApp",
                                   help_text="Numéro WhatsApp ex: 22890000000")
    phone       = models.CharField(max_length=20, blank=True, verbose_name="Téléphone",
                                   help_text="Numéro de téléphone affiché")
    is_active   = models.BooleanField(default=True, verbose_name="Actif")
    is_featured = models.BooleanField(default=False, verbose_name="Mis en avant")
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at  = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        ordering = ['-is_featured', '-created_at']
        verbose_name = "Service"
        verbose_name_plural = "Services"

    def __str__(self):
        return self.title


# ─────────────────────────────
# 📩 DEMANDE DE CONTACT
# ─────────────────────────────
class ServiceContact(models.Model):
    service    = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='contacts', verbose_name="Service")
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Utilisateur"
    )
    name       = models.CharField(max_length=100, verbose_name="Nom")
    phone      = models.CharField(max_length=20, verbose_name="Téléphone")
    message    = models.TextField(verbose_name="Message")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    is_read    = models.BooleanField(default=False, verbose_name="Lu")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Demande de contact"
        verbose_name_plural = "Demandes de contact"

    def __str__(self):
        return f"{self.name} → {self.service.title}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Envoi automatique d'email à l'admin du service
        if is_new:
            admin_email = self.service.admin.email
            if admin_email:
                try:
                    send_mail(
                        subject=f"[Lantante Technologie] Nouvelle demande : {self.service.title}",
                        message=(
                            f"Bonjour,\n\n"
                            f"Vous avez reçu une nouvelle demande de contact pour le service « {self.service.title} ».\n\n"
                            f"Nom : {self.name}\n"
                            f"Téléphone : {self.phone}\n"
                            f"Message :\n{self.message}\n\n"
                            f"Connectez-vous à l'administration pour répondre.\n\n"
                            f"— Lantante Technologie"
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[admin_email],
                        fail_silently=True,
                    )
                except Exception:
                    pass