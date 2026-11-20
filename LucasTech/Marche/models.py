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


def _code_espace():
    import secrets
    return secrets.token_urlsafe(12)


class Vendeur(models.Model):
    STATUTS = [('en_attente', 'En attente'), ('valide', 'Actif'), ('suspendu', 'Suspendu'), ('expire', 'Expiré')]
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
    # Espace vendeur séparé : lien propre à chaque vendeur + connexion obligatoire
    code = models.CharField("Code du lien", max_length=32, unique=True, default=_code_espace, editable=False)
    debut_acces = models.DateField("Début de l'accès", null=True, blank=True)
    fin_acces = models.DateField("Fin de l'accès", null=True, blank=True, help_text="Vide = sans limite.")
    slug = models.SlugField("Adresse de la boutique", max_length=140, unique=True, null=True, blank=True,
                            help_text="Lien public : /shop/vendeur/<adresse>/ (rempli automatiquement).")
    activation = models.CharField(max_length=64, blank=True, editable=False)
    logo = models.ImageField("Logo", upload_to='vendeurs/logos/', blank=True)
    telephone = models.CharField("Téléphone", max_length=30, blank=True)
    description = models.TextField("Description", blank=True)
    # Mini-site du vendeur (/vendeur/<adresse>/)
    banniere = models.ImageField("Image de bannière", upload_to='vendeurs/bannieres/', blank=True)
    slogan = models.CharField("Phrase d'accueil", max_length=140, blank=True)
    couleur = models.CharField("Couleur principale", max_length=7, default='#0F6B3E',
                               help_text="Code couleur, ex. #0F6B3E")
    email_contact = models.EmailField("E-mail de contact", blank=True)
    facebook = models.URLField("Facebook", blank=True)
    instagram = models.URLField("Instagram", blank=True)
    tiktok = models.URLField("TikTok", blank=True)
    youtube = models.URLField("YouTube", blank=True)
    x = models.URLField("X (Twitter)", blank=True)
    telegram = models.URLField("Telegram", blank=True)
    site_web = models.URLField("Site web", blank=True)
    chaine_whatsapp = models.URLField("Lien de ma chaîne WhatsApp", blank=True,
                                      help_text="Ex. https://whatsapp.com/channel/…")
    texte_chaine = models.CharField("Texte du bouton de la chaîne", max_length=60, blank=True,
                                    default="Rejoindre ma chaîne WhatsApp")
    created_at = models.DateTimeField("Créé le", auto_now_add=True)

    class Meta:
        verbose_name = "Vendeur"
        verbose_name_plural = "Vendeurs"
        ordering = ['boutique']

    def __str__(self):
        return self.boutique

    @property
    def actif(self):
        """Peut vendre : validé, ni suspendu, et accès pas encore terminé."""
        from django.utils import timezone
        return self.statut == 'valide' and (self.fin_acces is None or self.fin_acces >= timezone.localdate())

    @property
    def etat(self):
        """(code, libellé) : actif, bientot (fin dans 7 jours ou moins), expire, suspendu, attente."""
        from django.utils import timezone
        if self.statut == 'suspendu':
            return 'suspendu', "Suspendu"
        if self.statut == 'en_attente':
            return 'attente', "En attente"
        if self.statut == 'expire' or not self.actif:
            return 'expire', "Expiré"
        if self.fin_acces and (self.fin_acces - timezone.localdate()).days <= 7:
            return 'bientot', "Expire bientôt"
        return 'actif', "Actif"

    def lien_espace(self):
        from django.urls import reverse
        return reverse('espace:connexion', args=[self.code])

    def lien_public(self):
        from django.urls import reverse
        return reverse('minisite:accueil', args=[self.slug]) if self.slug else ''

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slug_unique(self)
        super().save(*args, **kwargs)


def slug_unique(v):
    from django.utils.text import slugify
    base = (slugify(v.boutique) or 'boutique')[:120]
    s, i = base, 2
    while Vendeur.objects.filter(slug=s).exclude(pk=v.pk).exists():
        s, i = f'{base}-{i}', i + 1
    return s


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


def nom_piece_contact(instance, filename):
    """Nom de fichier aléatoire (rien ne révèle la personne ni le fichier d'origine)."""
    import os
    import secrets
    ext = os.path.splitext(filename)[1].lower()[:6] or '.bin'
    return f"vendeurs/pieces-contact/{secrets.token_hex(16)}{ext}"


class ContactVendeur(models.Model):
    """« Vendre sur Lantante » : court formulaire de prise de contact (sans pièce d'identité).
    L'équipe rappelle le vendeur puis crée son espace."""
    STATUTS = [('nouvelle', "Nouvelle"), ('contactee', "Contactée"), ('compte_cree', "Compte créé"), ('refusee', "Refusée")]
    PIECES = [('cni', "Carte d'identité"), ('electeur', "Carte d'électeur"), ('passeport', "Passeport"),
              ('permis', "Permis de conduire")]
    CATEGORIES = [('vetements', "Vêtements"), ('chaussures', "Chaussures"), ('accessoires', "Accessoires"),
                  ('electronique', "Électronique"), ('livres', "Livres"), ('alimentation', "Alimentation"),
                  ('beaute', "Beauté"), ('autre', "Autre")]
    statut = models.CharField("Statut", max_length=12, choices=STATUTS, default='nouvelle', db_index=True)
    boutique = models.CharField("Nom de la boutique", max_length=120)
    nom = models.CharField("Nom", max_length=120)
    prenom = models.CharField("Prénom", max_length=120, blank=True)
    telephone = models.CharField("Téléphone / WhatsApp", max_length=20)
    email = models.EmailField("E-mail")
    ville = models.CharField("Ville", max_length=80)
    categorie = models.CharField("Ce que vous vendez", max_length=20, choices=CATEGORIES, blank=True)
    message = models.TextField("Message", blank=True)
    # Pièce d'identité : stockage privé, visible par l'équipe seulement, jamais supprimée automatiquement
    piece_type = models.CharField("Type de pièce", max_length=10, choices=PIECES, blank=True)
    piece = models.FileField("Pièce d'identité", upload_to=nom_piece_contact, storage=_prive, blank=True)
    piece_verifiee = models.BooleanField("Pièce vérifiée", default=False)
    consentement = models.BooleanField("Accord pour la vérification de la pièce", default=False)
    vendeur = models.ForeignKey(Vendeur, on_delete=models.SET_NULL, null=True, blank=True, related_name='contacts',
                                verbose_name="Vendeur créé")
    note = models.TextField("Note de l'équipe", blank=True)
    created_at = models.DateTimeField("Reçue le", auto_now_add=True)

    class Meta:
        verbose_name = "Demande de contact vendeur"
        verbose_name_plural = "Demandes de contact vendeurs"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.boutique} — {self.nom_complet}"

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip()

    def lien_whatsapp(self):
        from urllib.parse import quote
        n = ''.join(c for c in self.telephone if c.isdigit())
        return f"https://wa.me/{n}?text={quote(f'Bonjour {self.prenom or self.nom}, ici Lantante. Merci pour votre demande pour « {self.boutique} ».')}"


class SectionSite(models.Model):
    """Bloc de la page d'accueil du mini-site d'un vendeur : titre, texte, image."""
    vendeur = models.ForeignKey(Vendeur, on_delete=models.CASCADE, related_name='sections')
    titre = models.CharField("Titre", max_length=120)
    texte = models.TextField("Texte", blank=True)
    image = models.ImageField("Image", upload_to='vendeurs/sections/', blank=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        verbose_name = "Section du site"
        verbose_name_plural = "Sections du site"
        ordering = ['ordre', 'pk']

    def __str__(self):
        return self.titre
