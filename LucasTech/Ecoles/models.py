"""Écoles : fiche, photos et filières qui défilent, inscriptions ; chaque école gère son espace avec
ses collaborateurs (MembreEcole)."""
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from Payments.models import private_storage

CYCLES = [('primaire', 'Primaire'), ('college', 'Collège'), ('lycee', 'Lycée'),
          ('superieur', 'Université / Supérieur'), ('autre', 'Autre')]
CLASSES = {
    'primaire': ['CP1', 'CP2', 'CE1', 'CE2', 'CM1', 'CM2'],
    'college': ['6e', '5e', '4e', '3e'],
    'lycee': ['2nde', '1re', 'Tle'],
}
NIVEAUX = ['Bac', 'Bac+1', 'Bac+2', 'Bac+3', 'Bac+4', 'Bac+5']
SERIES_BAC = ['A', 'C', 'D', 'E', 'F', 'G', 'Autre']


class Ecole(models.Model):
    TYPES = [('primaire', 'École primaire'), ('college', 'Collège'), ('lycee', 'Lycée'),
             ('universite', 'Université'), ('centre', 'Centre de formation')]
    nom = models.CharField("Nom", max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    type = models.CharField("Type", max_length=12, choices=TYPES)
    ville = models.CharField("Ville", max_length=80, blank=True)
    logo = models.ImageField("Logo", upload_to='ecoles/logos/', blank=True)
    couverture = models.ImageField("Photo principale", upload_to='ecoles/couvertures/', blank=True)
    description = models.TextField("Présentation", blank=True)
    telephone = models.CharField("Téléphone", max_length=30, blank=True)
    whatsapp = models.CharField("WhatsApp", max_length=30, blank=True)
    email = models.EmailField("E-mail", blank=True)
    site_web = models.URLField("Site web", blank=True)
    cycles = models.JSONField("Cycles", default=list, blank=True,
                              help_text="Primaire, Collège, Lycée, Université / Supérieur, Autre (plusieurs possibles).")
    inscriptions_ouvertes = models.BooleanField("Inscriptions ouvertes", default=True)
    publie = models.BooleanField("Publiée", default=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)
    created_at = models.DateTimeField("Créée le", auto_now_add=True)

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "École"
        verbose_name_plural = "Écoles"

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nom)[:160] or 'ecole'
            slug, i = base, 2
            while Ecole.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, i = f'{base}-{i}', i + 1
            self.slug = slug
        super().save(*args, **kwargs)


class PhotoEcole(models.Model):
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField("Photo", upload_to='ecoles/photos/')
    legende = models.CharField("Légende", max_length=120, blank=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = "Photo"
        verbose_name_plural = "Photos (bande défilante)"


class Filiere(models.Model):
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='filieres')
    cycle = models.CharField("Cycle", max_length=10, choices=CYCLES, default='superieur')
    nom = models.CharField("Filière", max_length=140)
    niveau = models.CharField("Niveau", max_length=60, blank=True)
    duree = models.CharField("Durée", max_length=40, blank=True)
    frais = models.PositiveIntegerField("Frais (CFA)", null=True, blank=True)
    image = models.ImageField("Photo", upload_to='ecoles/filieres/', blank=True)
    description = models.TextField("Description", blank=True)
    ouverte = models.BooleanField("Ouverte aux inscriptions", default=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "Filière"
        verbose_name_plural = "Filières"

    def __str__(self):
        return f"{self.nom} — {self.ecole}"


class InscriptionEcole(models.Model):
    STATUTS = [('nouvelle', 'Nouvelle'), ('contactee', 'Contactée'), ('inscrite', 'Inscrite'), ('refusee', 'Refusée')]
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='inscriptions', verbose_name="École")
    filiere = models.ForeignKey(Filiere, on_delete=models.SET_NULL, null=True, blank=True, related_name='inscriptions',
                                verbose_name="Filière")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='inscriptions_ecoles', verbose_name="Compte")
    nom = models.CharField("Nom", max_length=100)
    prenom = models.CharField("Prénom", max_length=100)
    telephone = models.CharField("Téléphone", max_length=30)
    email = models.EmailField("E-mail", blank=True)
    niveau_actuel = models.CharField("Niveau actuel", max_length=80, blank=True)
    cycle = models.CharField("Cycle", max_length=10, choices=CYCLES, blank=True)
    classe = models.CharField("Classe", max_length=10, blank=True)
    niveau_etudes = models.CharField("Niveau", max_length=10, blank=True)
    serie_bac = models.CharField("Série du Bac", max_length=10, blank=True)
    document = models.FileField("Document", storage=private_storage, upload_to='ecoles/documents/%Y/', blank=True,
                                validators=[FileExtensionValidator(['pdf', 'jpg', 'jpeg', 'png', 'webp'])])
    message = models.TextField("Message", blank=True)
    statut = models.CharField("Statut", max_length=10, choices=STATUTS, default='nouvelle')
    created_at = models.DateTimeField("Reçue le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"

    def __str__(self):
        return f"{self.prenom} {self.nom} — {self.ecole}"


class MembreEcole(models.Model):
    ROLES = [('proprietaire', 'Responsable'), ('collaborateur', 'Collaborateur')]
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='membres')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ecoles_gerees',
                             verbose_name="Utilisateur")
    role = models.CharField("Rôle", max_length=14, choices=ROLES, default='collaborateur')

    class Meta:
        unique_together = [('ecole', 'user')]
        verbose_name = "Membre de l'équipe"
        verbose_name_plural = "Équipe de l'école (accès à cet espace)"

    def __str__(self):
        return f"{self.user} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        donner_acces_admin(self.user)


GROUPE = "Gestion d'école"


def donner_acces_admin(user):
    """Un membre d'école peut se connecter à l'admin et ne voit que son école (voir admin.py)."""
    from django.contrib.auth.models import Group, Permission
    g, _ = Group.objects.get_or_create(name=GROUPE)
    perms = Permission.objects.filter(content_type__app_label='Ecoles')
    g.permissions.add(*perms)
    user.groups.add(g)
    if not user.is_staff:
        user.is_staff = True
        user.save(update_fields=['is_staff'])



class NouveauteEcole(models.Model):
    """Opportunités et nouveautés d'une école : bande qui défile et section de la fiche."""
    ecole = models.ForeignKey(Ecole, on_delete=models.CASCADE, related_name='nouveautes')
    titre = models.CharField("Titre", max_length=120)
    image = models.ImageField("Image", upload_to='ecoles/nouveautes/', blank=True)
    texte = models.CharField("Texte court", max_length=300, blank=True)
    date = models.DateField("Date", default=timezone.localdate)
    publie = models.BooleanField("Publiée", default=True)

    class Meta:
        ordering = ['-date', '-id']
        verbose_name = "Nouveauté"
        verbose_name_plural = "Nouveautés et opportunités"

    def __str__(self):
        return self.titre
