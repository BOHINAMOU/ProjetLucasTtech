import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

PENDING_HOLD = timedelta(minutes=20)  # places gardées pendant un paiement en cours


class Event(models.Model):
    title = models.CharField(max_length=200, verbose_name="Titre")
    slug = models.SlugField(max_length=220, unique=True, blank=True, verbose_name="Slug (URL)")
    description = models.TextField(verbose_name="Description")
    location = models.CharField(max_length=200, verbose_name="Lieu",
                                help_text="Ex : Palais des Congrès, Lomé")
    map_url = models.URLField(blank=True, verbose_name="Lien Google Maps (optionnel)")
    starts_at = models.DateTimeField(verbose_name="Date et heure de début")
    ends_at = models.DateTimeField(null=True, blank=True, verbose_name="Fin (optionnel)")
    cover = models.ImageField(upload_to='events/', verbose_name="Photo de couverture")
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='organized_events', verbose_name="Organisateur",
                                  help_text="Il ne verra que ses propres événements et ventes "
                                            "(espace organisateur : /evenements/organisateur/).")
    is_published = models.BooleanField(default=True, verbose_name="Publié")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['starts_at']
        verbose_name = "Événement"
        verbose_name_plural = "Événements"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or 'evenement'
            slug, i = base, 2
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f'{base}-{i}', i + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('events:detail', args=[self.slug])

    @property
    def is_past(self):
        return (self.ends_at or self.starts_at) < timezone.now()

    @property
    def min_price(self):
        prices = [t.price for t in self.ticket_types.all()]
        return min(prices) if prices else None


class TicketType(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='ticket_types',
                              verbose_name="Événement")
    name = models.CharField(max_length=100, verbose_name="Nom", help_text="Ex : Standard, VIP, Étudiant")
    description = models.CharField(max_length=200, blank=True, verbose_name="Détail (optionnel)",
                                   help_text="Ex : accès zone VIP, boisson offerte")
    image = models.ImageField(upload_to='events/tickets/', blank=True, null=True, verbose_name="Photo du ticket",
                              help_text="Photo de couverture du lot (sinon, celle de l'événement).")
    price = models.PositiveIntegerField(verbose_name="Prix (FCFA)", help_text="0 = gratuit")
    quantity = models.PositiveIntegerField(verbose_name="Nombre de places")
    max_per_order = models.PositiveIntegerField(default=10, verbose_name="Maximum par commande")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    class Meta:
        ordering = ['order', 'price']
        verbose_name = "Type de ticket"
        verbose_name_plural = "Types de tickets"

    def __str__(self):
        return f"{self.event.title} — {self.name}"

    @property
    def sold(self):
        return self.tickets.count()

    def held(self):
        """Places réservées par des paiements encore en cours (moins de 20 min)."""
        from Payments.models import Payment
        since = timezone.now() - PENDING_HOLD
        total = 0
        for items in Payment.objects.filter(event_id=self.event_id, status='pending',
                                            created_at__gte=since).values_list('items', flat=True):
            for it in items or []:
                if it.get('ticket_type') == self.pk:
                    total += int(it.get('quantity') or 0)
        return total

    @property
    def remaining(self):
        return max(0, self.quantity - self.sold - self.held())

    @property
    def cover(self):
        return self.image or self.event.cover

    def max_choice(self):
        return min(self.remaining, self.max_per_order)

    def choice_range(self):
        return range(0, self.max_choice() + 1)


def _ticket_code():
    return secrets.token_hex(4).upper()


class Ticket(models.Model):
    code = models.CharField(max_length=12, unique=True, default=_ticket_code, verbose_name="Code")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tickets', verbose_name="Événement")
    ticket_type = models.ForeignKey(TicketType, on_delete=models.PROTECT, related_name='tickets',
                                    verbose_name="Type")
    payment = models.ForeignKey('Payments.Payment', on_delete=models.CASCADE, related_name='tickets',
                                verbose_name="Paiement")
    holder_name = models.CharField(max_length=200, verbose_name="Au nom de")
    used_at = models.DateTimeField(null=True, blank=True, verbose_name="Validé à l'entrée le")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Ticket vendu"
        verbose_name_plural = "Tickets vendus"

    def __str__(self):
        return f"{self.code} — {self.ticket_type}"
