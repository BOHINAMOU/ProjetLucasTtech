"""Marketplace : vendeurs partenaires, réglages de livraison, reversements."""
from decimal import Decimal

from django.conf import settings
from django.db import models


class ReglageLivraison(models.Model):
    """Tarif de livraison dans la même ville : base + prix par km (un seul réglage)."""
    tarif_base = models.PositiveIntegerField("Tarif de base (F)", default=500)
    prix_km = models.PositiveIntegerField("Prix par km (F)", default=100)
    rayon_ville_km = models.PositiveIntegerField(
        "Rayon « même ville » (km)", default=25,
        help_text="Au-delà de cette distance du point de retrait, le prix fixe « autre ville » du produit s'applique.")
    depart_ville = models.CharField("Ville de départ par défaut", max_length=80, default="Lomé")
    depart_latitude = models.DecimalField("Latitude par défaut", max_digits=9, decimal_places=6, default=6.175300,
                                          help_text="Université de Lomé : pour les produits sans emplacement.")
    depart_longitude = models.DecimalField("Longitude par défaut", max_digits=9, decimal_places=6, default=1.212800)
    distance_defaut_km = models.PositiveIntegerField(
        "Distance par défaut (km)", default=5,
        help_text="Utilisée quand l'acheteur saisit seulement sa ville (sans position GPS).")

    class Meta:
        verbose_name = "Réglage de livraison"
        verbose_name_plural = "Réglage de livraison"

    def __str__(self):
        return f"{self.tarif_base} CFA + {self.prix_km} CFA/km"

    @classmethod
    def load(cls):
        return cls.objects.first() or cls.objects.create()


class Vendeur(models.Model):
    STATUTS = [('en_attente', 'En attente'), ('valide', 'Validé'), ('suspendu', 'Suspendu')]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='vendeur',
                                verbose_name="Compte")
    boutique = models.CharField("Nom de la boutique", max_length=120)
    whatsapp = models.CharField("WhatsApp", max_length=30, help_text="Format : 22890000000.")
    ville = models.CharField("Ville", max_length=80)
    adresse_retrait = models.CharField("Point de retrait", max_length=200, blank=True)
    latitude = models.DecimalField("Latitude", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("Longitude", max_digits=9, decimal_places=6, null=True, blank=True)
    commission_pct = models.DecimalField("Commission Lantante (%)", max_digits=5, decimal_places=2,
                                         default=Decimal('10'))
    numero_reversement = models.CharField("Numéro de reversement", max_length=30, blank=True,
                                          help_text="Mobile Money où l'on reverse ses ventes.")
    statut = models.CharField("Statut", max_length=12, choices=STATUTS, default='en_attente')
    created_at = models.DateTimeField("Créé le", auto_now_add=True)

    class Meta:
        verbose_name = "Vendeur"
        verbose_name_plural = "Vendeurs"
        ordering = ['boutique']

    def __str__(self):
        return self.boutique

    @property
    def actif(self):
        return self.statut == 'valide'

    def save(self, *a, **kw):
        super().save(*a, **kw)
        if self.actif:
            from .acces import donner_acces
            donner_acces(self.user)


class Reversement(models.Model):
    """Argent reversé à un vendeur (trace de chaque virement)."""
    vendeur = models.ForeignKey(Vendeur, on_delete=models.PROTECT, related_name='reversements')
    montant = models.PositiveIntegerField("Montant (F)")
    date = models.DateField("Date")
    reference = models.CharField("Référence du transfert", max_length=80, blank=True)
    note = models.CharField("Note", max_length=200, blank=True)
    par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='+', editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Reversement"
        verbose_name_plural = "Reversements aux vendeurs"
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.vendeur} — {self.montant} CFA"


class CategorieVendeur(models.Model):
    """Rayon privé d'un vendeur pour ranger SES produits (jamais montré dans l'appli ni à l'équipe)."""
    vendeur = models.ForeignKey(Vendeur, on_delete=models.CASCADE, related_name='categories')
    nom = models.CharField("Nom", max_length=80)

    class Meta:
        verbose_name = "Ma catégorie"
        verbose_name_plural = "Mes catégories"
        ordering = ['nom']
        unique_together = [('vendeur', 'nom')]

    def __str__(self):
        return self.nom


def _jeton():
    import secrets
    return secrets.token_urlsafe(32)


def _prive():
    from Payments.models import private_storage
    return private_storage()


class DemandeVendeur(models.Model):
    """« Vendre sur Lantante » : demande sans compte, suivie par un lien privé ; l'équipe accepte, corrige ou refuse."""
    STATUTS = [('en_attente', "En vérification"), ('a_corriger', "À corriger"), ('refusee', "Refusée"),
               ('acceptee', "Acceptée")]
    PIECES = [('cni', "Carte nationale d'identité"), ('electeur', "Carte d'électeur"), ('passeport', "Passeport")]

    jeton = models.CharField(max_length=64, unique=True, default=_jeton, editable=False)
    statut = models.CharField("Statut", max_length=12, choices=STATUTS, default='en_attente', db_index=True)
    motif = models.TextField("Motif (à corriger / refus)", blank=True)
    boutique = models.CharField("Nom de la boutique", max_length=120)
    prenom = models.CharField("Prénom du responsable", max_length=80)
    nom = models.CharField("Nom du responsable", max_length=80)
    telephone = models.CharField("Téléphone", max_length=30)
    whatsapp = models.CharField("WhatsApp", max_length=30)
    email = models.EmailField("E-mail")
    ville = models.CharField("Ville", max_length=80)
    activite = models.CharField("Ce que vous vendez", max_length=200)
    piece_type = models.CharField("Type de pièce", max_length=10, choices=PIECES)
    piece_numero = models.CharField("Numéro de la pièce", max_length=40)
    piece = models.FileField("Pièce d'identité (recto et verso)", upload_to='vendeurs/pieces/', storage=_prive)
    vendeur = models.OneToOneField(Vendeur, on_delete=models.SET_NULL, null=True, blank=True, related_name='demande')
    decide_le = models.DateTimeField("Décision le", null=True, blank=True)
    created_at = models.DateTimeField("Déposée le", auto_now_add=True)
    updated_at = models.DateTimeField("Modifiée le", auto_now=True)

    class Meta:
        verbose_name = "Demande vendeur"
        verbose_name_plural = "Demandes vendeurs"
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.boutique} ({self.get_statut_display()})"

    @property
    def numero(self):
        return f"V{self.pk:05d}" if self.pk else ''

    @property
    def modifiable(self):
        return self.statut in ('en_attente', 'a_corriger')

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('vendre:suivi', args=[self.jeton])
