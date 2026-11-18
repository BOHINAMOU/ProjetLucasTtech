"""Répétiteur - École : professeurs et répétiteurs, contactés directement (WhatsApp, e-mail, appel)."""
from django.core.exceptions import ValidationError
from django.db import models


def ajouter_mois(d, n):
    """Même jour, n mois plus tard (le dernier jour du mois si ce jour n'existe pas)."""
    import calendar
    import datetime
    m = d.month - 1 + n
    annee, mois = d.year + m // 12, m % 12 + 1
    return datetime.date(annee, mois, min(d.day, calendar.monthrange(annee, mois)[1]))


def whatsapp_togo(valeur):
    """Numéro WhatsApp : 8 chiffres togolais, avec ou sans +228 / espaces. Renvoie 228XXXXXXXX."""
    chiffres = ''.join(c for c in (valeur or '') if c.isdigit())
    if len(chiffres) == 8:
        chiffres = '228' + chiffres
    if len(chiffres) != 11 or not chiffres.startswith('228'):
        raise ValidationError("Numéro WhatsApp invalide : +228 suivi de 8 chiffres (ex. +228 90 12 34 56).")
    return chiffres


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
    whatsapp = models.CharField("WhatsApp", max_length=30, blank=True,
                                help_text="Obligatoire (sauf exemple) : +228 suivi de 8 chiffres.")
    email = models.EmailField("E-mail", blank=True)
    telephone = models.CharField("Téléphone", max_length=30, blank=True)
    actif = models.BooleanField("Visible", default=True)
    fin_affichage = models.DateField("Visible jusqu'au", null=True, blank=True,
                                     help_text="Après cette date, le profil disparaît de l'appli. Vide = sans limite.")
    rappel_fin_envoye = models.DateField("Rappel de fin envoyé pour", null=True, blank=True, editable=False)
    est_exemple = models.BooleanField("Exemple", default=False,
                                      help_text="Profil de démonstration (supprimable en un clic : action « Supprimer tous les exemples »).")
    est_service_lantante = models.BooleanField(
        "Cours Lantante", default=False,
        help_text="Fiche de cours proposée par Lantante (pas une personne) : contact = WhatsApp principal du site. "
                  "Affichée après les vrais répétiteurs.")
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)
    created_at = models.DateTimeField("Ajouté le", auto_now_add=True)

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "Répétiteur"
        verbose_name_plural = "Répétiteur - École"

    def __str__(self):
        return self.nom

    @property
    def expire(self):
        from django.utils import timezone
        return bool(self.fin_affichage and self.fin_affichage < timezone.localdate())

    def clean(self):
        # un vrai répétiteur doit toujours être joignable sur WhatsApp
        if not self.est_exemple and not self.est_service_lantante:
            try:
                self.whatsapp = whatsapp_togo(self.whatsapp)
            except ValidationError as e:
                raise ValidationError({'whatsapp': e.messages})

    @property
    def liste_matieres(self):
        return [m.strip() for m in self.matieres.split(',') if m.strip()]


# ── Candidatures : un répétiteur remplit le formulaire du site, paie, puis l'équipe vérifie ──

def _stockage_prive():
    """Pièces d'identité : hors de /media/ (jamais publiques), lues seulement par l'équipe via une vue protégée."""
    from Payments.models import private_storage
    return private_storage()


def _jeton():
    import secrets
    return secrets.token_urlsafe(32)


class ReglageCandidature(models.Model):
    prix = models.PositiveIntegerField("Frais de candidature (CFA)", default=2000)

    class Meta:
        verbose_name = verbose_name_plural = "Frais de candidature"

    def __str__(self):
        return f"{self.prix} CFA"

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]


class Candidature(models.Model):
    STATUTS = [
        ('a_payer', "En attente de paiement"),
        ('a_verifier', "Payé, en vérification"),
        ('a_corriger', "À corriger"),
        ('rejetee', "Rejeté"),
        ('validee', "Validé"),
    ]
    PIECES = [('cni', "Carte nationale d'identité"), ('electeur', "Carte d'électeur"), ('passeport', "Passeport")]

    user = models.ForeignKey('Users.User', on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='candidatures_repetiteur', verbose_name="Compte (facultatif)")
    jeton = models.CharField("Jeton du lien de suivi", max_length=64, unique=True, default=_jeton, editable=False)
    statut = models.CharField("Statut", max_length=12, choices=STATUTS, default='a_payer', db_index=True)
    motif = models.TextField("Motif (à corriger / rejet)", blank=True)
    # identité
    prenom = models.CharField("Prénom", max_length=80)
    nom = models.CharField("Nom", max_length=80)
    telephone = models.CharField("Téléphone", max_length=30)
    whatsapp = models.CharField("WhatsApp", max_length=30, help_text="+228 suivi de 8 chiffres.")
    email = models.EmailField("E-mail", blank=True)
    # profil
    photo = models.ImageField("Photo", upload_to='repetiteurs/candidatures/')
    matieres = models.CharField("Matières", max_length=250, help_text="Séparées par des virgules.")
    niveaux = models.CharField("Niveaux", max_length=200, blank=True)
    ville = models.CharField("Ville", max_length=80)
    quartier = models.CharField("Quartier", max_length=120, blank=True)
    latitude = models.DecimalField("Latitude", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("Longitude", max_digits=9, decimal_places=6, null=True, blank=True)
    experience = models.CharField("Expérience", max_length=200, blank=True)
    description = models.TextField("Présentation", blank=True)
    tarif = models.CharField("Tarif", max_length=80, blank=True)
    # pièce d'identité (privée)
    piece_type = models.CharField("Type de pièce", max_length=10, choices=PIECES)
    piece_numero = models.CharField("Numéro de la pièce", max_length=40)
    piece_recto = models.FileField("Pièce : recto", upload_to='candidatures/pieces/', storage=_stockage_prive)
    piece_verso = models.FileField("Pièce : verso", upload_to='candidatures/pieces/', storage=_stockage_prive, blank=True)
    # suivi
    paiement = models.ForeignKey('Payments.Payment', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='candidatures', verbose_name="Paiement")
    repetiteur = models.OneToOneField(Repetiteur, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='candidature', verbose_name="Fiche publiée")
    decide_le = models.DateTimeField("Décision finale le", null=True, blank=True)
    pieces_supprimees = models.BooleanField("Pièce supprimée", default=False)
    created_at = models.DateTimeField("Déposée le", auto_now_add=True)
    updated_at = models.DateTimeField("Modifiée le", auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Candidature répétiteur"
        verbose_name_plural = "Candidatures répétiteurs"

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.get_statut_display()})"

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip()

    @property
    def numero(self):
        return f"R{self.pk:05d}" if self.pk else ''

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('repetiteurs:suivi', args=[self.jeton])

    @property
    def modifiable(self):
        return self.statut in ('a_payer', 'a_corriger')


class HistoriqueCandidature(models.Model):
    candidature = models.ForeignKey(Candidature, on_delete=models.CASCADE, related_name='historique')
    date = models.DateTimeField(auto_now_add=True)
    auteur = models.CharField("Par", max_length=150, blank=True)
    action = models.CharField("Action", max_length=120)
    motif = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']
        verbose_name = "Historique"
        verbose_name_plural = "Historique"

    def __str__(self):
        return self.action
