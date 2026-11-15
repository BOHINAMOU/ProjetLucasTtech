import secrets

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.urls import reverse


def private_storage():
    """Fichiers vendus (PDF) : hors du dossier public /media/, servis seulement après paiement."""
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


def _new_reference():
    return 'LT' + secrets.token_hex(6).upper()


def _new_token():
    return secrets.token_urlsafe(24)


class Payment(models.Model):
    KIND_CHOICES = [
        ('service', 'Service'),
        ('formation', 'Formation'),
        ('shop', 'Commande boutique (panier)'),
        ('product', 'Produit de la boutique'),
        ('ticket', "Tickets d'événement"),
        ('abonnement', 'Abonnement concours'),
        ('soutien', "Soutien d'un événement"),
        ('concours', "Accès à un concours"),
        ('depot', "Recharge du solde"),
        ('acces', "Abonnement Accès Épreuves"),
    ]
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('approved', 'Payé'),
        ('declined', 'Refusé'),
        ('canceled', 'Annulé'),
        ('refunded', 'Remboursé'),
    ]

    reference = models.CharField(max_length=20, unique=True, default=_new_reference, editable=False,
                                 verbose_name="Référence")
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, verbose_name="Type")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True,
                              verbose_name="Statut")
    amount = models.PositiveIntegerField(verbose_name="Montant (FCFA)")
    description = models.CharField(max_length=255, verbose_name="Description")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='payments', verbose_name="Compte")
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name = models.CharField(max_length=100, verbose_name="Nom")
    phone = models.CharField(max_length=30, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    whatsapp = models.CharField(max_length=30, blank=True, verbose_name="WhatsApp")
    city = models.CharField(max_length=255, blank=True, verbose_name="Localité")
    address = models.CharField(max_length=255, blank=True, verbose_name="Adresse de livraison")
    operator = models.CharField(max_length=20, blank=True, verbose_name="Opérateur Mobile Money")
    failure_reason = models.CharField(max_length=255, blank=True, verbose_name="Motif de l'échec")

    service = models.ForeignKey('Services.Service', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='payments', verbose_name="Service")
    formation = models.ForeignKey('Formations.Formation', on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='payments', verbose_name="Formation")
    shop_order = models.ForeignKey('Shop.ShopOrder', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='payments', verbose_name="Commande boutique")
    product = models.ForeignKey('Shop.Product', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='payments', verbose_name="Produit")
    contest = models.ForeignKey('concours.Contest', on_delete=models.PROTECT, null=True, blank=True,
                                related_name='payments', verbose_name="Concours")
    event = models.ForeignKey('Events.Event', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='payments', verbose_name="Événement")
    vendeur = models.ForeignKey('Marche.Vendeur', on_delete=models.PROTECT, null=True, blank=True,
                                related_name='paiements', verbose_name="Vendeur")
    livraison = models.PositiveIntegerField("Livraison (F)", default=0)
    livraison_detail = models.CharField("Détail livraison", max_length=120, blank=True)
    remise = models.PositiveIntegerField("Remise (F)", default=0)
    code_promo = models.ForeignKey('CodePromo', on_delete=models.PROTECT, null=True, blank=True,
                                   related_name='paiements', verbose_name="Code promo")
    commission = models.PositiveIntegerField("Commission Lantante (F)", default=0)
    items = models.JSONField(default=list, blank=True, verbose_name="Détail",
                             help_text="Tickets demandés : [{ticket_type, name, quantity, price}]")

    mode = models.CharField(max_length=10, default='sandbox', verbose_name="Mode",
                            help_text="sandbox (test), live (réel) ou demo (local sans clés)")
    fedapay_id = models.CharField(max_length=40, blank=True, db_index=True, verbose_name="ID transaction FedaPay")
    payment_url = models.URLField(max_length=500, blank=True, verbose_name="Lien de paiement")
    access_token = models.CharField(max_length=64, default=_new_token, editable=False)
    fulfilled = models.BooleanField(default=False, verbose_name="Livré",
                                    help_text="Accès / tickets / commande validés après paiement.")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Payé le")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Paiement en ligne"
        verbose_name_plural = "Paiements en ligne"

    def __str__(self):
        return f"{self.reference} — {self.description} ({self.get_status_display()})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def operator_label(self):
        from .mobile_money import operator_label
        return operator_label(self.operator)

    @property
    def operator_short(self):
        """« Mixx by Yas (ex T-Money) » -> « Mixx by Yas »."""
        return self.operator_label.split(' (')[0]

    @property
    def phone_display(self):
        from .mobile_money import pretty
        return pretty(self.phone)

    @property
    def is_paid(self):
        return self.status == 'approved'

    @property
    def sold_item(self):
        return self.service or self.formation

    @property
    def downloadable_file(self):
        """Le PDF livré après paiement (service ou formation), s'il existe."""
        obj = self.sold_item
        f = getattr(obj, 'file', None) if obj else None
        return f if f else None

    def get_absolute_url(self):
        return reverse('payments:result', args=[self.reference]) + f'?t={self.access_token}'



class Portefeuille(models.Model):
    """Solde Lantante d'un utilisateur : rechargé par Mobile Money, utilisé pour payer dans Lantante.
    Pas de retrait (non remboursable en espèces). Le solde ne bouge QUE via Payments.solde (mouvements tracés)."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='portefeuille',
                                verbose_name="Utilisateur")
    solde = models.PositiveIntegerField("Solde (FCFA)", default=0, editable=False)
    updated_at = models.DateTimeField("Mis à jour", auto_now=True)

    class Meta:
        verbose_name = "Portefeuille"
        verbose_name_plural = "Soldes des utilisateurs"

    def __str__(self):
        return f"{self.user} — {self.solde} F"


class MouvementSolde(models.Model):
    TYPES = [('depot', 'Dépôt'), ('paiement', 'Paiement'), ('remboursement', 'Remboursement'),
             ('ajustement', "Ajustement par l'équipe")]
    portefeuille = models.ForeignKey(Portefeuille, on_delete=models.PROTECT, related_name='mouvements')
    type = models.CharField("Type", max_length=14, choices=TYPES)
    montant = models.IntegerField("Montant (FCFA)", help_text="Positif = crédit, négatif = débit.")
    solde_apres = models.PositiveIntegerField("Solde après")
    payment = models.ForeignKey('Payment', on_delete=models.PROTECT, null=True, blank=True, related_name='mouvements_solde',
                                verbose_name="Paiement lié")
    motif = models.CharField("Motif", max_length=255, blank=True)
    par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='+', verbose_name="Fait par")
    created_at = models.DateTimeField("Date", auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = "Mouvement du solde"
        verbose_name_plural = "Mouvements des soldes"
        constraints = [
            # un paiement Mobile Money ne crédite le solde qu'UNE fois, même si le webhook arrive deux fois
            models.UniqueConstraint(fields=['payment', 'type'], name='un_mouvement_par_paiement_et_type'),
        ]

    def __str__(self):
        return f"{self.get_type_display()} {self.montant:+} F"



class CodePromo(models.Model):
    TYPES = [('pct', 'Pourcentage'), ('montant', 'Montant fixe')]
    code = models.CharField("Code", max_length=30, unique=True, help_text="Lettres et chiffres, ex. RENTREE25.")
    type = models.CharField("Type", max_length=8, choices=TYPES, default='pct')
    valeur = models.PositiveIntegerField("Valeur", help_text="% ou F selon le type.")
    debut = models.DateTimeField("Début", null=True, blank=True)
    fin = models.DateTimeField("Fin", null=True, blank=True)
    max_utilisations = models.PositiveIntegerField("Utilisations max. (total)", null=True, blank=True,
                                                   help_text="Vide = illimité.")
    max_par_personne = models.PositiveIntegerField("Utilisations max. par personne", null=True, blank=True, default=1,
                                                   help_text="Vide = illimité.")
    minimum_achat = models.PositiveIntegerField("Achat minimum (F)", default=0)
    actif = models.BooleanField("Actif", default=True)
    produits = models.ManyToManyField('Shop.Product', blank=True, verbose_name="Produits")
    concours = models.ManyToManyField('concours.Contest', blank=True, verbose_name="Concours")
    formations = models.ManyToManyField('Formations.Formation', blank=True, verbose_name="Formations")
    evenements = models.ManyToManyField('Events.Event', blank=True, verbose_name="Événements")
    vendeurs = models.ManyToManyField('Marche.Vendeur', blank=True, verbose_name="Vendeurs")
    abonnement = models.BooleanField("Abonnement Accès Épreuves", default=False)
    created_at = models.DateTimeField("Créé le", auto_now_add=True)

    class Meta:
        verbose_name = "Code promo"
        verbose_name_plural = "Codes promo"
        ordering = ['-created_at']

    def __str__(self):
        return self.code

    def save(self, *a, **kw):
        self.code = ''.join(self.code.split()).upper()
        super().save(*a, **kw)
