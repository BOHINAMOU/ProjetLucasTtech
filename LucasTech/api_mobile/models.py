"""Documents enregistrés hors connexion par chaque utilisateur (gardés côté serveur) : après une
réinstallation, l'application propose « Récupérer mes téléchargements » en un geste."""
from django.conf import settings
from django.db import models


class OfflineDocument(models.Model):
    KIND_CHOICES = [('epreuve', 'Sujet'), ('corrige', 'Corrigé')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offline_documents',
                             verbose_name="Utilisateur")
    kind = models.CharField("Type", max_length=10, choices=KIND_CHOICES)
    doc_id = models.PositiveIntegerField("Document")
    titre = models.CharField("Titre", max_length=200, blank=True)
    sous_titre = models.CharField("Sous-titre", max_length=200, blank=True)
    created_at = models.DateTimeField("Enregistré le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('user', 'kind', 'doc_id')]
        verbose_name = "Document hors connexion"
        verbose_name_plural = "Documents hors connexion"

    def __str__(self):
        return f"{self.user} — {self.kind} {self.doc_id}"
