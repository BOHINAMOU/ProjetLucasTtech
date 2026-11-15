"""Répétiteur - École : professeurs et répétiteurs, contactés directement (WhatsApp, e-mail, appel)."""
from django.db import models


class Repetiteur(models.Model):
    photo = models.ImageField("Photo", upload_to='repetiteurs/', blank=True)
    nom = models.CharField("Nom", max_length=120)
    matieres = models.CharField("Spécialités / matières", max_length=250,
                                help_text="Séparées par des virgules : Mathématiques, Physique-Chimie…")
    niveaux = models.CharField("Niveaux enseignés", max_length=200, blank=True, help_text="Ex. CM2, 3e, Tle, Université")
    ville = models.CharField("Ville", max_length=80)
    quartier = models.CharField("Quartier", max_length=120, blank=True)
    latitude = models.DecimalField("Latitude", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("Longitude", max_digits=9, decimal_places=6, null=True, blank=True)
    description = models.TextField("Présentation", blank=True)
    experience = models.CharField("Expérience", max_length=200, blank=True, help_text="Ex. 8 ans, professeur certifié")
    tarif = models.CharField("Tarif", max_length=80, blank=True, help_text="Facultatif. Ex. 15 000 CFA / mois")
    whatsapp = models.CharField("WhatsApp", max_length=30, blank=True, help_text="Format : 22890000000")
    email = models.EmailField("E-mail", blank=True)
    telephone = models.CharField("Téléphone", max_length=30, blank=True)
    actif = models.BooleanField("Visible", default=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)
    created_at = models.DateTimeField("Ajouté le", auto_now_add=True)

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "Répétiteur"
        verbose_name_plural = "Répétiteur - École"

    def __str__(self):
        return self.nom

    @property
    def liste_matieres(self):
        return [m.strip() for m in self.matieres.split(',') if m.strip()]
