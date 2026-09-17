from django.db import models
from django.conf import settings


# ─────────────────────────────
# 📢 ANNONCE / BANDEAU
# ─────────────────────────────
class Announcement(models.Model):
    message    = models.TextField(verbose_name="Message")
    is_active  = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.message[:60]


# ─────────────────────────────
# 🤝 BANDEAU COLLABORATION / FOURNISSEURS
# ─────────────────────────────
class CollabBanner(models.Model):
    message = models.CharField(
        max_length=300,
        default="Vous êtes une entreprise ou un fournisseur ? Contactez-nous pour une "
                 "collaboration et proposez vos produits sur notre boutique.",
        verbose_name="Message",
    )
    whatsapp_number = models.CharField(
        max_length=30, default="22890000000", verbose_name="Numéro WhatsApp",
        help_text="Numéro complet, ex : 22890000000",
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        verbose_name = "Bandeau collaboration"
        verbose_name_plural = "Bandeau collaboration"

    def __str__(self):
        return self.message[:60]


# ─────────────────────────────
# 📂 CATÉGORIE
# ─────────────────────────────
class Category(models.Model):
    name        = models.CharField(max_length=100, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    icon        = models.CharField(max_length=50, blank=True, verbose_name="Icône", help_text="Classe Font Awesome ex: fa-mobile")
    slug        = models.SlugField(unique=True, verbose_name="Slug (URL)")
    order       = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


# ─────────────────────────────
# 📦 PRODUIT
# ─────────────────────────────
class Product(models.Model):
    category     = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products', verbose_name="Catégorie")
    name         = models.CharField(max_length=255, db_index=True, verbose_name="Nom")  # 🔥 index pour recherche rapide
    description  = models.TextField(verbose_name="Description")
    price        = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix")
    old_price    = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Ancien prix",
        help_text="Ancien prix (avant réduction). Laisser vide si le produit n'est pas en promotion."
    )
    bulk_price   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Prix en gros", help_text="Prix en gros")
    bulk_min_qty = models.PositiveIntegerField(default=10, verbose_name="Quantité min. (prix en gros)", help_text="Quantité min pour prix en gros")
    image        = models.ImageField(upload_to='shop/products/', blank=True, null=True, verbose_name="Image")
    video        = models.FileField(upload_to='shop/videos/', blank=True, null=True, verbose_name="Vidéo")
    stock        = models.PositiveIntegerField(default=0, verbose_name="Stock")
    is_available = models.BooleanField(default=True, verbose_name="Disponible")
    is_featured  = models.BooleanField(default=False, verbose_name="Mis en avant")
    created_at   = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at   = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def is_in_stock(self):
        return self.stock > 0

    @property
    def is_on_sale(self):
        return bool(self.old_price and self.old_price > self.price)

    @property
    def discount_percent(self):
        if not self.is_on_sale:
            return 0
        return round((self.old_price - self.price) / self.old_price * 100)


# ─────────────────────────────
# 🖼️ PHOTOS SUPPLÉMENTAIRES (galerie produit)
# ─────────────────────────────
class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name="Produit")
    image   = models.ImageField(upload_to='shop/products/gallery/', verbose_name="Image")
    order   = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Photo de {self.product.name}"


# ─────────────────────────────
# 🛒 PANIER
# ─────────────────────────────
class ShopCart(models.Model):
    user       = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shop_cart', verbose_name="Utilisateur")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    def total_price(self):
        return sum(item.total_price() for item in self.items.all())

    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    def __str__(self):
        return f"Panier de {self.user.email}"


class ShopCartItem(models.Model):
    cart     = models.ForeignKey(ShopCart, on_delete=models.CASCADE, related_name='items', verbose_name="Panier")
    product  = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Produit")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantité")

    def total_price(self):
        return self.quantity * self.product.price

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


# Fichier : Shop/models.py
# ... (tous vos modèles jusqu'à ShopCartItem restent les mêmes) ...


# ─────────────────────────────
# 💳 COMMANDE
# ─────────────────────────────

class ShopOrder(models.Model):
    # DÉFINITION DES CHOIX UNE SEULE FOIS
    STATUS_CHOICES = [
        ('pending',          'En attente de paiement'),
        ('paid',             'Payée'),
        ('cash_on_delivery', 'Paiement en espèces à la livraison'),
        ('shipped',          'Expédiée'),
        ('delivered',        'Livrée'),
        ('cancelled',        'Annulée'),
    ]
    PAYMENT_CHOICES = [
        ('whatsapp',  'WhatsApp'),
        ('flooz',     'Flooz'),
        ('tmoney',    'T-Money'),
        ('wave',      'Wave'),
        ('cash',      'Espèces'),
    ]

    # TOUS LES CHAMPS DU MODÈLE ENSEMBLE
    user           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shop_orders', verbose_name="Utilisateur")
    total_price    = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix total")
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Statut")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='cash', verbose_name="Moyen de paiement")
    receipt_number = models.CharField(max_length=20, blank=True, verbose_name="Numéro de reçu")
    created_at     = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    
    # NOUVEAUX CHAMPS POUR LE PAIEMENT EN ESPÈCES
    cash_delivery_name = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nom pour la livraison")
    cash_delivery_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Téléphone pour la livraison")
    cash_delivery_message = models.TextField(blank=True, null=True, verbose_name="Message pour la livraison")

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            import secrets
            self.receipt_number = 'LT-' + secrets.token_hex(4).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Commande #{self.receipt_number} — {self.user.email}"


# Le modèle ShopOrderItem reste le même
class ShopOrderItem(models.Model):
    order    = models.ForeignKey(ShopOrder, on_delete=models.CASCADE, related_name='items', verbose_name="Commande")
    product  = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Produit")
    quantity = models.PositiveIntegerField(verbose_name="Quantité")
    price    = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix")

    def total_price(self):
        return self.quantity * self.price

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


# ... (le reste de vos modèles Reservation et Review restent les mêmes) ...

# ─────────────────────────────
# 📅 RÉSERVATION
# ─────────────────────────────
class Reservation(models.Model):
    STATUS_CHOICES = [
        ('pending',   'En attente'),
        ('confirmed', 'Confirmée'),
        ('cancelled', 'Annulée'),
    ]

    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reservations', null=True, blank=True, verbose_name="Utilisateur")
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reservations', verbose_name="Produit")
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name  = models.CharField(max_length=100, verbose_name="Nom")
    phone      = models.CharField(max_length=20, verbose_name="Téléphone")
    whatsapp   = models.CharField(max_length=20, blank=True, verbose_name="WhatsApp")
    email      = models.EmailField(blank=True, verbose_name="Email")
    quantity   = models.PositiveIntegerField(default=1, verbose_name="Quantité")
    notes      = models.TextField(blank=True, verbose_name="Notes")
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Statut")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    def __str__(self):
        return f"Réservation {self.first_name} {self.last_name} — {self.product.name}"


# ─────────────────────────────
# ⭐ AVIS / REVIEW
# ─────────────────────────────
class Review(models.Model):
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews', verbose_name="Produit")
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Utilisateur")
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name  = models.CharField(max_length=100, blank=True, verbose_name="Nom")
    email      = models.EmailField(blank=True, verbose_name="Email")
    rating     = models.PositiveSmallIntegerField(
        default=5, verbose_name="Note",
        choices=[(i, i) for i in range(1, 6)]
    )
    comment    = models.TextField(verbose_name="Commentaire")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Avis de {self.first_name} sur {self.product.name}"
    