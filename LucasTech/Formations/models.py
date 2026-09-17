from django.db import models
from django.conf import settings


class Formation(models.Model):
    LEVEL_CHOICES = [
        ('debutant',     'Débutant'),
        ('intermediaire','Intermédiaire'),
        ('avance',       'Avancé'),
    ]
    TYPE_CHOICES = [
        ('cours',       'Formation payante en ligne (panier + WhatsApp)'),
        ('inscription', 'Inscription par formulaire (groupe WhatsApp)'),
        ('numerique',   'Formation numérique à télécharger (PDF / Word / Excel)'),
    ]

    formation_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default='cours',
        verbose_name="Type de formation"
    )
    whatsapp_group_link = models.URLField(
        blank=True, verbose_name="Lien du groupe WhatsApp",
        help_text="Envoyé par email après inscription (type « Inscription par formulaire »)."
    )
    file = models.FileField(
        upload_to='formations/fichiers/', blank=True, null=True,
        verbose_name="Fichier à télécharger",
        help_text="PDF, Word ou Excel — accessible uniquement après paiement confirmé (type « Formation numérique »)."
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="formations", verbose_name="Auteur"
    )
    title        = models.CharField(max_length=255, verbose_name="Titre")
    description  = models.TextField(verbose_name="Description")
    what_you_learn = models.TextField(
        blank=True, verbose_name="Ce que vous allez apprendre",
        help_text="Un point par ligne."
    )
    price        = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix")
    old_price    = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Ancien prix",
        help_text="Ancien prix (avant réduction). Laisser vide si pas de promotion."
    )
    level        = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='debutant', verbose_name="Niveau")
    duration     = models.CharField(max_length=60, blank=True, verbose_name="Durée", help_text="Ex : 4 semaines, 12h de vidéo")
    students_count = models.PositiveIntegerField(default=0, verbose_name="Nombre d'inscrits")
    image        = models.ImageField(upload_to='formations/', verbose_name="Image")
    is_published = models.BooleanField(default=True, verbose_name="Publié")
    is_featured  = models.BooleanField(default=False, verbose_name="Mis en avant")
    created_at   = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at   = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_on_sale(self):
        return bool(self.old_price and self.old_price > self.price)

    @property
    def discount_percent(self):
        if not self.is_on_sale:
            return 0
        return round((self.old_price - self.price) / self.old_price * 100)

    def learn_points(self):
        return [l.strip() for l in self.what_you_learn.splitlines() if l.strip()]


class Cart(models.Model):
    user       = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart", verbose_name="Utilisateur"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    def total_price(self):
        return sum(item.total_price() for item in self.items.all())

    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    def __str__(self):
        return f"Panier de {self.user.email}"


class CartItem(models.Model):
    cart      = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items", verbose_name="Panier")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, verbose_name="Formation")
    quantity  = models.PositiveIntegerField(default=1, verbose_name="Quantité")

    def total_price(self):
        return self.quantity * self.formation.price

    def __str__(self):
        return f"{self.formation.title} x {self.quantity}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending',   'En attente'),
        ('paid',      'Payé'),
        ('cancelled', 'Annulé'),
    ]
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders", verbose_name="Utilisateur"
    )
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix total")
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Statut")
    created_at  = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    def __str__(self):
        return f"Commande #{self.id} — {self.user.email}"


class OrderItem(models.Model):
    order     = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="Commande")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, verbose_name="Formation")
    quantity  = models.PositiveIntegerField(verbose_name="Quantité")
    price     = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix")

    def total_price(self):
        return self.quantity * self.price

    def __str__(self):
        return f"{self.formation.title} x {self.quantity}"


def user_has_purchased(user, formation):
    """True si l'utilisateur a une commande PAYÉE contenant cette formation
    (donne le droit de télécharger une formation numérique à vie)."""
    if not user or not user.is_authenticated:
        return False
    return OrderItem.objects.filter(
        order__user=user, order__status='paid', formation=formation
    ).exists()


# ─────────────────────────────
# 📝 INSCRIPTION PAR FORMULAIRE (formations type "inscription")
# ─────────────────────────────
class Registration(models.Model):
    formation  = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name='registrations', verbose_name="Formation")
    country    = models.CharField(max_length=100, verbose_name="Pays")
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name  = models.CharField(max_length=100, verbose_name="Nom")
    whatsapp_country_code = models.CharField(max_length=6, default='+228', verbose_name="Indicatif")
    whatsapp_number = models.CharField(max_length=20, verbose_name="Numéro WhatsApp")
    email      = models.EmailField(verbose_name="Email")
    motivation = models.TextField(blank=True, verbose_name="Message de motivation")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"

    def __str__(self):
        return f"{self.first_name} {self.last_name} — {self.formation.title}"

    @property
    def whatsapp_full_number(self):
        return f"{self.whatsapp_country_code} {self.whatsapp_number}"