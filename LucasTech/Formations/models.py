from django.db import models
from django.conf import settings


class Formation(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="formations"
    )
    title        = models.CharField(max_length=255)
    description  = models.TextField()
    price        = models.DecimalField(max_digits=10, decimal_places=2)
    image        = models.ImageField(upload_to='formations/')
    is_published = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Cart(models.Model):
    user       = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def total_price(self):
        return sum(item.total_price() for item in self.items.all())

    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    def __str__(self):
        return f"Panier de {self.user.email}"


class CartItem(models.Model):
    cart      = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE)
    quantity  = models.PositiveIntegerField(default=1)

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
        related_name="orders"
    )
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Commande #{self.id} — {self.user.email}"


class OrderItem(models.Model):
    order     = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE)
    quantity  = models.PositiveIntegerField()
    price     = models.DecimalField(max_digits=10, decimal_places=2)

    def total_price(self):
        return self.quantity * self.price

    def __str__(self):
        return f"{self.formation.title} x {self.quantity}"