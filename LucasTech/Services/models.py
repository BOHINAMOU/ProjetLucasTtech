from django.db import models
from django.conf import settings
from django.core.mail import send_mail


# ─────────────────────────────
# 📂 CATÉGORIE DE SERVICE
# ─────────────────────────────
class ServiceCategory(models.Model):
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon        = models.CharField(max_length=60, blank=True, help_text="Classe Font Awesome ex: fa-code")
    slug        = models.SlugField(unique=True)
    order       = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'Service Categories'

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
        null=True, blank=True, related_name='services'
    )
    title       = models.CharField(max_length=255)
    description = models.TextField()
    image       = models.ImageField(upload_to='services/', blank=True, null=True)
    video       = models.FileField(upload_to='services/videos/', blank=True, null=True)
    price_from  = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                      help_text="Prix à partir de (optionnel)")
    whatsapp    = models.CharField(max_length=20, blank=True,
                                   help_text="Numéro WhatsApp ex: 22890000000")
    phone       = models.CharField(max_length=20, blank=True,
                                   help_text="Numéro de téléphone affiché")
    is_active   = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_featured', '-created_at']

    def __str__(self):
        return self.title


# ─────────────────────────────
# 📩 DEMANDE DE CONTACT
# ─────────────────────────────
class ServiceContact(models.Model):
    service    = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='contacts')
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    name       = models.CharField(max_length=100)
    phone      = models.CharField(max_length=20)
    message    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read    = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

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
                        subject=f"[LucasTech] Nouvelle demande : {self.service.title}",
                        message=(
                            f"Bonjour,\n\n"
                            f"Vous avez reçu une nouvelle demande de contact pour le service « {self.service.title} ».\n\n"
                            f"Nom : {self.name}\n"
                            f"Téléphone : {self.phone}\n"
                            f"Message :\n{self.message}\n\n"
                            f"Connectez-vous à l'administration pour répondre.\n\n"
                            f"— LucasTech"
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[admin_email],
                        fail_silently=True,
                    )
                except Exception:
                    pass