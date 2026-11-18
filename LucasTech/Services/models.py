from django.db import models
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from Payments.models import private_storage


# ─────────────────────────────
# 📂 CATÉGORIE DE SERVICE
# ─────────────────────────────

# Icône et couleur dans l'appli (même style que « Explorez nos services »)
ICONES_APPLI = [
    # (code, libellé) ; marques : logos officiels (Font Awesome), sinon icônes Material
    ('widgets', 'Grille'), ('language', 'Site web'), ('phone_android', 'Application mobile'), ('code', 'Code'),
    ('storefront', 'Boutique en ligne'), ('shopping_bag', 'Commande'), ('campaign', 'Publicité'),
    ('trending_up', 'Marketing'), ('smart_toy', 'Automatisation / IA'), ('person_add', 'Création de compte'),
    ('share', 'Réseaux sociaux'), ('youtube', 'YouTube'), ('tiktok', 'TikTok'), ('facebook', 'Facebook'),
    ('instagram', 'Instagram'), ('whatsapp', 'WhatsApp'), ('windows', 'Windows'), ('microsoft', 'Microsoft Office'),
    ('description', 'Document'), ('settings', 'Configuration'), ('computer', 'Ordinateur / système'),
    ('build', 'Dépannage'), ('backup', 'Sauvegarde'), ('wifi', 'Réseau WiFi'), ('security', 'Sécurité'),
    ('cloud', 'Cloud'), ('key', 'Activation / licence'), ('brush', 'Graphisme'), ('photo_camera', 'Photo / vidéo'),
    ('print', 'Impression'), ('school', 'Formation'), ('support_agent', 'Assistance'),
    ('local_shipping', 'Livraison'), ('music_note', 'Musique'),
]
MARQUES = {'youtube', 'tiktok', 'facebook', 'instagram', 'whatsapp', 'windows', 'microsoft'}
COULEURS_APPLI = [('vert', 'Vert'), ('bleu', 'Bleu'), ('violet', 'Violet'), ('orange', 'Orange'), ('rose', 'Rose'),
                  ('cyan', 'Cyan'), ('rouge', 'Rouge'), ('gris', 'Gris')]

class ServiceCategory(models.Model):
    name        = models.CharField(max_length=100, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    icon        = models.CharField(max_length=60, blank=True, verbose_name="Icône", help_text="Classe Font Awesome ex: fa-code")
    slug        = models.SlugField(unique=True, verbose_name="Slug (URL)")
    order       = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    image       = models.ImageField("Photo", upload_to='services/categories/', blank=True,
                                    help_text="Affichée dans l'appli à la place de l'icône.")
    icone_appli = models.CharField("Icône dans l'appli", max_length=20, choices=ICONES_APPLI, default='widgets')
    couleur     = models.CharField("Couleur dans l'appli", max_length=10, choices=COULEURS_APPLI, default='vert')
    parent      = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sous_categories',
                                    verbose_name="Grande catégorie",
                                    help_text="Vide = grande catégorie (carte de la page Services, ex. « Services numériques »).")

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
    icone_appli = models.CharField("Icône dans l'appli", max_length=20, choices=ICONES_APPLI, blank=True,
                                   help_text="Vide = icône de la catégorie.")
    couleur     = models.CharField("Couleur dans l'appli", max_length=10, choices=COULEURS_APPLI, blank=True,
                                   help_text="Vide = couleur de la catégorie.")
    image       = models.ImageField(upload_to='services/', blank=True, null=True, verbose_name="Image")
    video       = models.FileField(upload_to='services/videos/', blank=True, null=True, verbose_name="Vidéo")
    price_from  = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Prix à partir de",
                                      help_text="Prix à partir de (optionnel)")
    price       = models.PositiveIntegerField(null=True, blank=True, verbose_name="Prix payable en ligne (CFA)",
                                      help_text="Si rempli, un bouton « Payer » (FedaPay) apparaît sur la page du service.")
    file        = models.FileField(upload_to='services/fichiers/', storage=private_storage, blank=True, null=True,
                                   verbose_name="PDF remis après paiement",
                                   help_text="Téléchargé automatiquement par le client après un paiement réussi.")
    whatsapp    = models.CharField(max_length=20, blank=True, verbose_name="WhatsApp",
                                   help_text="Numéro WhatsApp ex: 22890000000")
    phone       = models.CharField(max_length=20, blank=True, verbose_name="Téléphone",
                                   help_text="Numéro de téléphone affiché")
    is_active   = models.BooleanField(default=True, verbose_name="Actif")
    inscriptions_ouvertes = models.BooleanField(default=False, verbose_name="Inscriptions ouvertes",
                                                help_text="Affiche « S'inscrire » avec le formulaire ci-dessous. "
                                                          "Décochez pour clôturer.")
    is_featured = models.BooleanField(default=False, verbose_name="Mis en avant")
    clics_whatsapp = models.PositiveIntegerField("Contacts WhatsApp", default=0, editable=False)
    clics_support = models.PositiveIntegerField("Contacts support", default=0, editable=False)
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at  = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        ordering = ['-is_featured', '-created_at']
        verbose_name = "Service"
        verbose_name_plural = "Services"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('services:service_detail', args=[self.pk])

    @property
    def icon_class(self):
        return self.icon or (self.category.icon if self.category and self.category.icon else 'fa-laptop-code')


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


class ChampInscription(models.Model):
    """Champ du formulaire d'inscription d'un service (configuré dans l'admin)."""
    TYPES = [('texte', 'Texte'), ('long', 'Texte long'), ('nombre', 'Nombre'), ('telephone', 'Téléphone'),
             ('email', 'E-mail'), ('date', 'Date'), ('choix', 'Liste de choix')]
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='champs')
    libelle = models.CharField("Libellé", max_length=80)
    type = models.CharField("Type", max_length=10, choices=TYPES, default='texte')
    obligatoire = models.BooleanField("Obligatoire", default=True)
    choix = models.CharField("Choix (séparés par des virgules)", max_length=400, blank=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = "Champ du formulaire"
        verbose_name_plural = "Formulaire d'inscription"

    def __str__(self):
        return self.libelle

    def options(self):
        return [c.strip() for c in self.choix.split(',') if c.strip()]


class InscriptionService(models.Model):
    STATUTS = [('nouvelle', 'Nouvelle'), ('traitee', 'Traitée'), ('annulee', 'Annulée')]
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='inscriptions', verbose_name="Service")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='inscriptions_services', verbose_name="Compte")
    reponses = models.JSONField("Réponses", default=dict)
    statut = models.CharField("Statut", max_length=10, choices=STATUTS, default='nouvelle')
    created_at = models.DateTimeField("Reçue le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Inscription à un service"
        verbose_name_plural = "Inscriptions aux services"

    def __str__(self):
        return f"{self.service} — {self.created_at:%d/%m/%Y}"
