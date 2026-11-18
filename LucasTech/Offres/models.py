"""Emplois : offres publiées comme des actualités (photo, description, contacts) et candidatures depuis l'appli."""
from django.conf import settings
from django.db import models
from django.utils import timezone


def _prive():
    from Payments.models import private_storage
    return private_storage()


class OffreEmploi(models.Model):
    TYPES = [('cdi', 'CDI'), ('cdd', 'CDD'), ('stage', 'Stage'), ('mission', 'Mission'), ('freelance', 'Freelance'),
             ('autre', 'Autre')]
    titre = models.CharField("Titre", max_length=160)
    image = models.ImageField("Photo", upload_to='emplois/', blank=True)
    entreprise = models.CharField("Entreprise / recruteur", max_length=120)
    ville = models.CharField("Ville", max_length=80, default='Lomé')
    type_contrat = models.CharField("Type", max_length=10, choices=TYPES, default='cdi')
    description = models.TextField("Description")
    date_limite = models.DateField("Date limite", null=True, blank=True,
                                   help_text="Après cette date, l'offre disparaît toute seule.")
    telephone = models.CharField("Téléphone (Appeler)", max_length=30, blank=True)
    whatsapp = models.CharField("WhatsApp", max_length=30, blank=True)
    email_contact = models.EmailField("E-mail de contact", blank=True)
    lien = models.URLField("Lien de l'offre", blank=True)
    candidature_appli = models.BooleanField("Postuler dans l'appli", default=True)
    email_recruteur = models.EmailField("E-mail du recruteur (candidatures)", blank=True,
                                        help_text="Facultatif : pour lui transférer les candidatures.")
    notifier = models.BooleanField("Envoyer une notification à la publication", default=False)
    est_exemple = models.BooleanField("Exemple", default=False)
    publie = models.BooleanField("Publiée", default=True)
    vues = models.PositiveIntegerField("Vues", default=0, editable=False)
    notifie_le = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField("Publiée le", default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Offre d'emploi"
        verbose_name_plural = "Offres d'emploi"

    def __str__(self):
        return self.titre

    @property
    def active(self):
        return self.publie and (not self.date_limite or self.date_limite >= timezone.localdate())

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('offres:detail', args=[self.pk])


class OffreLue(models.Model):
    offre = models.ForeignKey(OffreEmploi, on_delete=models.CASCADE, related_name='+')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    lu_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('offre', 'user')]


class CandidatureEmploi(models.Model):
    STATUTS = [('recue', 'Reçue'), ('vue', 'Vue'), ('retenue', 'Retenue'), ('refusee', 'Refusée')]
    offre = models.ForeignKey(OffreEmploi, on_delete=models.CASCADE, related_name='candidatures')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='candidatures_emploi')
    nom = models.CharField("Nom", max_length=120)
    telephone = models.CharField("Téléphone", max_length=30)
    email = models.EmailField("E-mail", blank=True)
    cv = models.FileField("CV", upload_to='emplois/cv/', storage=_prive, blank=True)
    message = models.TextField("Message", blank=True)
    statut = models.CharField("Statut", max_length=8, choices=STATUTS, default='recue', db_index=True)
    envoyee_recruteur = models.BooleanField("Envoyée au recruteur", default=False)
    created_at = models.DateTimeField("Reçue le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('offre', 'user')]
        verbose_name = "Candidature"
        verbose_name_plural = "Candidatures"

    def __str__(self):
        return f"{self.nom} — {self.offre}"
