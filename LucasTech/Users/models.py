from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from datetime import timedelta
import secrets


# ─────────────────────────────
# 👤 USER MANAGER
# ─────────────────────────────
class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'adresse email est obligatoire.")
        email = self.normalize_email(email)
        user  = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff',     True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active',    True)
        return self.create_user(email, password, **extra_fields)


# ─────────────────────────────
# 👤 USER
# ─────────────────────────────
class User(AbstractUser):
    username = None   # On supprime le champ username

    email         = models.EmailField(unique=True)
    phone         = models.CharField(max_length=20, blank=True, null=True)
    avatar        = models.ImageField(upload_to='avatars/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    country       = models.CharField(max_length=100, blank=True, null=True)
    city          = models.CharField(max_length=100, blank=True, null=True)
    is_verified   = models.BooleanField(default=False)
    is_premium    = models.BooleanField(default=False)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email

    @property
    def public_name(self):
        """Nom affichable publiquement (jamais l'email, pour la confidentialité)."""
        full = self.get_full_name().strip()
        if full:
            return full
        return "Membre Lantante Technologie"


# ─────────────────────────────
# 🔑 CODE RESET MOT DE PASSE (OTP)
# ─────────────────────────────
class PasswordResetCode(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_codes')
    code       = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used    = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)

    def is_valid(self):
        return (not self.is_used) and (not self.is_expired())

    @staticmethod
    def generate_code():
        return str(secrets.randbelow(1000000)).zfill(6)

    def __str__(self):
        return f"{self.user.email} — {self.code}"