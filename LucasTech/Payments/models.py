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
    ]
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('approved', 'Payé'),
        ('declined', 'Refusé'),
        ('canceled', 'Annulé'),
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
    event = models.ForeignKey('Events.Event', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='payments', verbose_name="Événement")
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
