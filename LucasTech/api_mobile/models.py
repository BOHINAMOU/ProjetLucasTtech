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



class CarouselItem(models.Model):
    """Bande principale de l'accueil, choisie par l'admin (sinon : sélection automatique)."""
    CIBLES = [('publication', 'Actualité'), ('produit', 'Produit'), ('evenement', 'Événement'),
              ('formation', 'Formation'), ('service', 'Service'), ('concours', 'Concours'), ('lien', 'Lien interne')]
    image = models.ImageField("Image", upload_to='carrousel/',
                              help_text="Format large conseillé (1200 × 600). Si vide : l'image de l'élément ciblé.",
                              blank=True)
    titre = models.CharField("Titre court", max_length=80, blank=True,
                             help_text="Si vide : le titre de l'élément ciblé.")
    cible = models.CharField("Ouvre", max_length=12, choices=CIBLES)
    cible_id = models.PositiveIntegerField("N° de l'élément", null=True, blank=True,
                                           help_text="Numéro (ID) de l'actualité, du produit… visible dans son adresse admin.")
    lien = models.CharField("Lien interne", max_length=200, blank=True, help_text="Ex : /concours/ (pour « Lien interne »).")
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)
    actif = models.BooleanField("Actif", default=True)
    debut = models.DateTimeField("Début d'affichage", null=True, blank=True)
    fin = models.DateTimeField("Fin d'affichage", null=True, blank=True)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = "Élément du carrousel"
        verbose_name_plural = "Carrousel de l'accueil"

    def __str__(self):
        return self.titre or f"{self.get_cible_display()} {self.cible_id or self.lien}"


class Notification(models.Model):
    AUDIENCES = [('tous', 'Tous les utilisateurs'), ('groupe', 'Un groupe'), ('personne', 'Une personne')]
    titre = models.CharField("Titre", max_length=120)
    message = models.TextField("Message", max_length=600)
    audience = models.CharField("Destinataires", max_length=10, choices=AUDIENCES, default='tous')
    groupe = models.ForeignKey('auth.Group', on_delete=models.CASCADE, null=True, blank=True, verbose_name="Groupe")
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                                    related_name='notifications', verbose_name="Personne")
    cible = models.CharField("Ouvre (facultatif)", max_length=12, choices=CarouselItem.CIBLES, blank=True)
    cible_id = models.PositiveIntegerField("N° de l'élément", null=True, blank=True)
    lien = models.CharField("Lien interne", max_length=200, blank=True)
    automatique = models.BooleanField("Automatique", default=False, editable=False)
    created_at = models.DateTimeField("Envoyée le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return self.titre


class NotificationLue(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='lectures')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    lue_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('notification', 'user')]


class ArticleLu(models.Model):
    """Actualités déjà ouvertes (badge « Non lu » dans l'appli, synchronisé entre téléphones)."""
    publication = models.ForeignKey('Publications.Publication', on_delete=models.CASCADE, related_name='+')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    lu_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('publication', 'user')]
