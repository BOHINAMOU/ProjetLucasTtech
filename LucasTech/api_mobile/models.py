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
    """Bande de l'appli : éléments choisis dans l'admin, en premier et dans l'ordre ; le reste de la bande est complété automatiquement."""
    CIBLES = [('publication', 'Actualité'), ('produit', 'Produit'), ('evenement', 'Événement'),
              ('formation', 'Formation'), ('service', 'Service'), ('concours', 'Concours'), ('partenaire', 'Partenaire'),
              ('emploi', "Offre d'emploi"), ('hotel', 'Hôtel'), ('restaurant', 'Restaurant'), ('ecole', 'École'),
              ('vendeur', 'Boutique de vendeur'), ('lien', 'Lien interne')]
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
        verbose_name = "Élément de la bande"
        verbose_name_plural = "Bande de l'appli"

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



class Appareil(models.Model):
    """Téléphone qui reçoit les notifications push (jeton Firebase Cloud Messaging)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='appareils',
                             verbose_name="Utilisateur")
    jeton = models.CharField("Jeton FCM", max_length=255, unique=True)
    plateforme = models.CharField("Plateforme", max_length=10, blank=True)
    updated_at = models.DateTimeField("Vu le", auto_now=True)

    class Meta:
        verbose_name = "Téléphone (notifications)"
        verbose_name_plural = "Téléphones (notifications)"

    def __str__(self):
        return f"{self.user} ({self.plateforme})"


class TuileAccueil(models.Model):
    """Tuiles « Explorez nos services » de l'accueil de l'appli, réglées dans l'admin (sans mise à jour de l'appli).
    L'appli garde les dernières reçues ; hors ligne ou serveur ancien, elle affiche ses tuiles par défaut."""
    ICONES = [('course', 'Moto (course)'), ('concours', 'Concours'), ('emploi', 'Emploi'), ('boutique', 'Boutique'),
              ('formation', 'Formation'), ('ecole', 'École'), ('actualite', 'Actualités'), ('solde', 'Solde'),
              ('services', 'Services'), ('hotel', 'Hôtel'), ('logement', 'Logement'), ('restaurant', 'Restaurant'),
              ('evenement', 'Événement'), ('repetiteur', 'Répétiteur'), ('lien', 'Lien')]
    COULEURS = [('vert', 'Vert'), ('vert_fonce', 'Vert foncé'), ('brun', 'Brun'), ('orange', 'Orange'),
                ('bleu', 'Bleu'), ('violet', 'Violet'), ('cyan', 'Cyan'), ('rose', 'Rose'), ('gris', 'Gris'),
                ('rouge', 'Rouge')]
    DESTINATIONS = [('course', 'Commander une course'), ('concours', 'Concours'), ('emplois', "Recherche d'emploi"),
                    ('boutique', 'Boutique'), ('formations', 'Formations'), ('ecoles', 'Écoles'),
                    ('actualites', 'Actualités'), ('solde', 'Solde'), ('services', 'Services'), ('hotels', 'Hôtels'),
                    ('logements', 'Location'), ('restaurants', 'Restaurants'), ('evenements', 'Événements'),
                    ('repetiteurs', 'Répétiteurs'), ('url', 'Lien (URL)')]
    libelle = models.CharField("Libellé", max_length=40)
    icone = models.CharField("Icône", max_length=12, choices=ICONES)
    couleur = models.CharField("Couleur", max_length=12, choices=COULEURS, default='vert')
    destination = models.CharField("Ouvre", max_length=12, choices=DESTINATIONS)
    url = models.URLField("Lien (si « Lien »)", blank=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)
    active = models.BooleanField("Affichée", default=True)
    android = models.BooleanField("Android", default=True)
    ios = models.BooleanField("iPhone", default=True)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = "Tuile de l'accueil"
        verbose_name_plural = "Tuiles de l'accueil (appli)"

    def __str__(self):
        return self.libelle


class LieuConnu(models.Model):
    """Lieux connus (Lomé et ailleurs) proposés EN PREMIER dans la recherche de lieux de l'appli :
    marchés, pharmacies, écoles, hôtels, églises, carrefours… (OpenStreetMap les connaît mal au Togo)."""
    nom = models.CharField("Nom", max_length=120)
    quartier = models.CharField("Quartier / ville", max_length=120, blank=True)
    alias = models.CharField("Autres noms", max_length=200, blank=True, help_text="Ex. « Grand marché, Assigamé ».")
    lat = models.FloatField("Latitude")
    lng = models.FloatField("Longitude")
    active = models.BooleanField("Actif", default=True)

    class Meta:
        ordering = ['nom']
        verbose_name = "Lieu connu"
        verbose_name_plural = "Lieux connus (recherche de l'appli)"

    def __str__(self):
        return f"{self.nom}, {self.quartier}" if self.quartier else self.nom
