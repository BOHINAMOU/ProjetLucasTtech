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
        verbose_name = "Annonce"
        verbose_name_plural = "Annonces"

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
        verbose_name = "Bannière de collaboration"
        verbose_name_plural = "Bannières de collaboration"

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
    order       = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage",
                                              help_text="Plus petit = plus haut dans la boutique et l'appli.")

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Catégorie'
        verbose_name_plural = 'Catégories'

    def __str__(self):
        return self.name


# ─────────────────────────────
# 📦 PRODUIT
# ─────────────────────────────
class Product(models.Model):
    category     = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products', verbose_name="Catégorie")
    name         = models.CharField(max_length=255, db_index=True, verbose_name="Nom")  # 🔥 index pour recherche rapide
    short_description = models.CharField(
        max_length=160, blank=True, verbose_name="Description courte",
        help_text="Une phrase affichée sur la carte du produit dans la boutique "
                  "(ex : « Charge 2 téléphones à la fois, autonomie 4 jours »). "
                  "Laisser vide pour reprendre le début de la description complète."
    )
    description  = models.TextField(
        verbose_name="Description complète",
        help_text="Texte détaillé affiché sur la page du produit (caractéristiques, contenu du carton, garantie...). "
                  "Sautez une ligne pour faire un nouveau paragraphe."
    )
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
    contact_whatsapp = models.CharField(
        max_length=30, blank=True, verbose_name="Numéro WhatsApp de contact (spécifique)",
        help_text="Optionnel — utilisé à la place du numéro WhatsApp par défaut du site pour "
                   "le bouton \"Commander via WhatsApp\" de ce produit. Utile quand le produit "
                   "est revendu pour le compte d'un tiers (ex : un autre commerçant, un revendeur) "
                   "et que les commandes doivent lui arriver directement. Format : 22890000000."
    )
    vues = models.PositiveIntegerField("Vues", default=0, editable=False)
    clics_whatsapp = models.PositiveIntegerField("Clics WhatsApp", default=0, editable=False)
    MODES_COMMANDE = [('les_deux', "Payer ou commander sur WhatsApp"), ('payer', "Payer dans l'appli seulement"),
                      ('whatsapp', "Commander sur WhatsApp seulement")]
    mode_commande = models.CharField(
        "Mode de commande", max_length=10, choices=MODES_COMMANDE, default='les_deux',
        help_text="« WhatsApp » ouvre une discussion avec le vendeur (ou Lantante) avec la commande déjà écrite.")
    categorie_vendeur = models.ForeignKey('Marche.CategorieVendeur', on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='produits', verbose_name="Ma catégorie",
                                          help_text="Rangement privé du vendeur (non affiché dans l'appli).")
    vendeur = models.ForeignKey('Marche.Vendeur', on_delete=models.PROTECT, null=True, blank=True,
                                related_name='produits', verbose_name="Vendeur",
                                help_text="Vide = produit vendu par Lantante.")
    livrable = models.BooleanField(
        "Produit livrable", default=True,
        help_text="Décoché (formation, PDF, contenu numérique) : pas de frais de livraison, pas de position demandée.")
    livraison_autre_ville = models.PositiveIntegerField(
        "Livraison autre ville (F)", null=True, blank=True,
        help_text="Prix fixe d'envoi hors de la ville du vendeur. Vide = livraison seulement dans sa ville.")
    retrait_latitude = models.DecimalField("Latitude du point de départ", max_digits=9, decimal_places=6,
                                           null=True, blank=True, help_text="Choisissez sur la carte.")
    retrait_longitude = models.DecimalField("Longitude du point de départ", max_digits=9, decimal_places=6,
                                            null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at   = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Produit"
        verbose_name_plural = "Produits"

    def __str__(self):
        return self.name

    @classmethod
    def en_vente(cls):
        """Produits visibles par le public : disponibles, et vendeur actif (ni suspendu ni expiré)."""
        from django.db.models import Q
        from django.utils import timezone
        ok = Q(vendeur__statut='valide') & (Q(vendeur__fin_acces__isnull=True) | Q(vendeur__fin_acces__gte=timezone.localdate()))
        return cls.objects.filter(is_available=True).filter(Q(vendeur__isnull=True) | ok)

    @property
    def card_description(self):
        """Phrase courte de la carte boutique (description courte, sinon début de la description complète)."""
        if self.short_description:
            return self.short_description
        from django.utils.html import strip_tags
        from django.utils.text import Truncator
        return Truncator(strip_tags(self.description)).chars(110)

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
        verbose_name = "Image du produit"
        verbose_name_plural = "Images du produit"

    def __str__(self):
        return f"Photo de {self.product.name}"


# ─────────────────────────────
# 🛒 PANIER
# ─────────────────────────────
class ShopCart(models.Model):
    user       = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shop_cart', verbose_name="Utilisateur")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        verbose_name = "Panier"
        verbose_name_plural = "Paniers"

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

    class Meta:
        verbose_name = "Article du panier"
        verbose_name_plural = "Articles du panier"

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
        ('fedapay',   'Paiement en ligne (FedaPay)'),
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
        verbose_name = "Commande boutique"
        verbose_name_plural = "Commandes boutique"

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
    product  = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Produit")
    formation = models.ForeignKey('Formations.Formation', on_delete=models.SET_NULL, null=True, blank=True,
                                  verbose_name="Formation")
    quantity = models.PositiveIntegerField(verbose_name="Quantité")
    price    = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix")

    class Meta:
        verbose_name = "Article de la commande"
        verbose_name_plural = "Articles de la commande"

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

    class Meta:
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"

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
        verbose_name = "Avis client"
        verbose_name_plural = "Avis clients"

    def __str__(self):
        return f"Avis de {self.first_name} sur {self.product.name}"
    


class PanierAppli(models.Model):
    """Panier de l'application, gardé sur le compte (retrouvé sur un autre téléphone)."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='panier_appli')
    contenu = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Panier (appli)"
        verbose_name_plural = "Paniers (appli)"
