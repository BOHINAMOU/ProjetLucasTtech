"""Emplois : offres publiées comme des actualités (photo, description) ; on contacte directement le recruteur
(Appeler, WhatsApp, E-mail, lien « Postuler »). Aucune candidature n'est gérée chez nous."""
from django.conf import settings
from django.db import models
from django.utils import timezone


def _prive():
    """Gardé pour l'historique des migrations (ancienne table des candidatures)."""
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
    lien = models.URLField("Lien pour postuler", blank=True, help_text="Bouton « Postuler » : ouvre ce lien.")
    notifier = models.BooleanField("Envoyer une notification à la publication", default=False)
    est_exemple = models.BooleanField("Exemple", default=False)
    publie = models.BooleanField("Publiée", default=True)
    vues = models.PositiveIntegerField("Vues", default=0, editable=False)
    clics_appel = models.PositiveIntegerField("Clics Appeler", default=0, editable=False)
    clics_whatsapp = models.PositiveIntegerField("Clics WhatsApp", default=0, editable=False)
    clics_lien = models.PositiveIntegerField("Clics Postuler", default=0, editable=False)
    clics_email = models.PositiveIntegerField("Clics E-mail", default=0, editable=False)
    notifie_le = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField("Publiée le", default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Offre d'emploi"
        verbose_name_plural = "Offres d'emploi"

    def __str__(self):
        return self.titre

    def clean(self):
        from django.core.exceptions import ValidationError
        if not (self.telephone or self.whatsapp or self.lien or self.email_contact):
            raise ValidationError("Renseignez au moins un contact : téléphone, WhatsApp, lien ou e-mail.")

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
