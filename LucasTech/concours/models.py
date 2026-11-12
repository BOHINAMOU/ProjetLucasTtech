"""Catalogue des concours : catégories, concours, sessions (années), épreuves et corrigés.

Les fichiers d'épreuves et de corrigés sont rangés dans le stockage PRIVÉ (PRIVATE_MEDIA_ROOT,
hors /media/ public) et ne sont servis que par la vue `concours:file`, qui vérifie les droits
à chaque requête (voir concours.access)."""
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from Payments.models import private_storage

ALLOWED_EXT = ['pdf', 'jpg', 'jpeg', 'png', 'webp']


def _unique_slug(instance, base, field='slug'):
    base = slugify(base)[:70] or 'concours'
    slug, n = base, 2
    model = type(instance)
    while model.objects.filter(**{field: slug}).exclude(pk=instance.pk).exists():
        slug, n = f'{base}-{n}', n + 1
    return slug


class ContestCategory(models.Model):
    name = models.CharField("Nom", max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    icon = models.CharField("Icône Font Awesome", max_length=40, blank=True, help_text="Ex. fa-chalkboard-user")
    order = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Catégorie de concours"
        verbose_name_plural = "Catégories de concours"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(self, self.name)
        super().save(*args, **kwargs)


class ContestQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)


class Contest(models.Model):
    acronym = models.CharField("Sigle", max_length=30, help_text="Ex. ENS")
    name = models.CharField("Nom complet", max_length=200)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    category = models.ForeignKey(ContestCategory, on_delete=models.PROTECT, related_name='contests',
                                 verbose_name="Catégorie")
    country = models.CharField("Pays", max_length=60, default="Togo")
    logo = models.ImageField("Photo de profil", upload_to='concours/logos/', blank=True,
                             help_text="Logo ou photo de l'école, format carré conseillé (ex. 400 × 400).")
    cover = models.ImageField("Photo de couverture", upload_to='concours/couvertures/', blank=True,
                              help_text="Facultative : image large en haut de la carte et de la page "
                                        "(ex. 1200 × 600). Sinon, un fond vert élégant est utilisé.")
    photo_credit = models.CharField("Crédit photo", max_length=255, blank=True,
                                    help_text="Auteur et licence des photos, si elles ne vous appartiennent pas.")
    photo_credit_url = models.URLField("Lien du crédit photo", blank=True)
    description = models.TextField("Description", blank=True)
    is_demo = models.BooleanField("Démonstration", default=False,
                                  help_text="Exemple factice : badge « Démo » affiché, non sélectionnable dans un abonnement.")
    is_published = models.BooleanField("Publié", default=False,
                                       help_text="Décochez pour retirer le concours du site.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ContestQuerySet.as_manager()

    class Meta:
        ordering = ['acronym', 'name']
        verbose_name = "Concours"
        verbose_name_plural = "Concours"

    def __str__(self):
        return f"{self.acronym} — {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(self, self.acronym or self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('concours:detail', args=[self.slug])

    @property
    def short_acronym(self):
        """Sigle d'affichage : « ENS » pour « DEMO-ENS » (le badge Démo reste affiché à côté)."""
        return self.acronym[5:] if self.acronym.upper().startswith('DEMO-') else self.acronym

    @property
    def gradient(self):
        """Fond par défaut de la couverture (une teinte par catégorie)."""
        return f"cx-g{(self.category_id or 0) % 5}"


class ContestSession(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name='sessions', verbose_name="Concours")
    year = models.PositiveSmallIntegerField("Année")
    is_published = models.BooleanField("Publiée", default=True)

    class Meta:
        ordering = ['-year']
        unique_together = [('contest', 'year')]
        verbose_name = "Session (année)"
        verbose_name_plural = "Sessions (années)"

    def __str__(self):
        return f"{self.contest.acronym} {self.year}"

    def get_absolute_url(self):
        return reverse('concours:session', args=[self.contest.slug, self.year])


class Specialty(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name='specialties',
                                verbose_name="Concours")
    name = models.CharField("Spécialité", max_length=120)

    class Meta:
        ordering = ['name']
        unique_together = [('contest', 'name')]
        verbose_name = "Spécialité"
        verbose_name_plural = "Spécialités"

    def __str__(self):
        return f"{self.contest.acronym} — {self.name}"


class ExamPaper(models.Model):
    session = models.ForeignKey(ContestSession, on_delete=models.CASCADE, related_name='papers',
                                verbose_name="Session")
    specialty = models.ForeignKey(Specialty, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='papers', verbose_name="Spécialité (facultatif)")
    title = models.CharField("Titre", max_length=200)
    subject = models.CharField("Matière", max_length=120, blank=True)
    duration = models.CharField("Durée", max_length=40, blank=True, help_text="Ex. 3 h")
    coefficient = models.DecimalField("Coefficient", max_digits=4, decimal_places=1, null=True, blank=True)
    description = models.TextField("Description", blank=True)
    file = models.FileField("Fichier du sujet (PDF ou image)", storage=private_storage,
                            upload_to='concours/epreuves/%Y/', validators=[FileExtensionValidator(ALLOWED_EXT)])
    is_free = models.BooleanField("Gratuite", default=False,
                                  help_text="Indication seulement : la lecture exige toujours un compte et un abonnement.")
    is_published = models.BooleanField("Publiée", default=True)
    order = models.PositiveSmallIntegerField("Ordre", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'subject', 'title']
        verbose_name = "Épreuve"
        verbose_name_plural = "Épreuves"

    def __str__(self):
        return f"{self.session} — {self.title}"

    @property
    def contest(self):
        return self.session.contest

    def published_corrections(self):
        return [c for c in self.corrections.all() if c.is_published]


class Correction(models.Model):
    KIND_CHOICES = [('officiel', 'Corrigé officiel'), ('enseignant', "Corrigé d'enseignant")]

    paper = models.ForeignKey(ExamPaper, on_delete=models.CASCADE, related_name='corrections',
                              verbose_name="Épreuve")
    kind = models.CharField("Type", max_length=12, choices=KIND_CHOICES, default='enseignant')
    author = models.CharField("Auteur (facultatif)", max_length=120, blank=True)
    file = models.FileField("Fichier du corrigé (PDF ou image)", storage=private_storage,
                            upload_to='concours/corriges/%Y/', validators=[FileExtensionValidator(ALLOWED_EXT)])
    is_published = models.BooleanField("Publié", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['kind', 'created_at']
        verbose_name = "Corrigé"
        verbose_name_plural = "Corrigés"

    def __str__(self):
        return f"{self.get_kind_display()} — {self.paper.title}"

    @property
    def contest(self):
        return self.paper.session.contest
