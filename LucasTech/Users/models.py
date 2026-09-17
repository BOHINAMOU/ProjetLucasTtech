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

    email         = models.EmailField(unique=True, verbose_name="Email")
    phone         = models.CharField(max_length=20, blank=True, null=True, verbose_name="Téléphone")
    avatar        = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Photo de profil")
    date_of_birth = models.DateField(blank=True, null=True, verbose_name="Date de naissance")
    country       = models.CharField(max_length=100, blank=True, null=True, verbose_name="Pays")
    city          = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ville")
    is_verified   = models.BooleanField(default=False, verbose_name="Vérifié")
    is_premium    = models.BooleanField(default=False, verbose_name="Premium")
    created_at    = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at    = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

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
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_codes', verbose_name="Utilisateur")
    code       = models.CharField(max_length=6, verbose_name="Code")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    is_used    = models.BooleanField(default=False, verbose_name="Utilisé")

    class Meta:
        verbose_name = "Code de réinitialisation du mot de passe"
        verbose_name_plural = "Codes de réinitialisation du mot de passe"

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)

    def is_valid(self):
        return (not self.is_used) and (not self.is_expired())

    @staticmethod
    def generate_code():
        return str(secrets.randbelow(1000000)).zfill(6)

    def __str__(self):
        return f"{self.user.email} — {self.code}"