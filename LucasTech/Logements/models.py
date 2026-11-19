"""Logements à louer (chambres, studios, appartements, maisons) : Lantante fait l'intermédiaire."""
from django.db import models

TYPES = [('chambre', 'Chambre'), ('chambre_salon', 'Chambre salon'), ('studio', 'Studio'),
         ('appartement', 'Appartement'), ('maison', 'Maison'), ('villa', 'Villa'), ('bureau', 'Bureau / local')]
PERIODES = [('mois', 'par mois'), ('nuit', 'par nuit')]
COMPTEURS = [('', '—'), ('individuel', 'Compteur individuel'), ('commun', 'Compteur commun')]
EQUIPEMENTS = [
    ('wifi', 'Wi-Fi'), ('clim', 'Climatisation'), ('ventilateur', 'Ventilateur'), ('parking', 'Parking'),
    ('cuisine', 'Cuisine'), ('douche_interne', 'Douche interne'), ('wc_interne', 'WC interne'), ('carrelage', 'Carrelage'),
    ('plafond', 'Faux plafond'), ('forage', 'Forage / eau'), ('gardien', 'Gardien'), ('cloture', 'Clôture / portail'),
    ('balcon', 'Balcon'), ('tv', 'Télévision'), ('eau_chaude', 'Eau chaude'), ('groupe', 'Groupe électrogène'),
]
CODES = dict(EQUIPEMENTS)
STATUTS = [('publie', 'Publiée'), ('attente', 'En attente'), ('refuse', 'Refusée')]
ROLES = [('proprietaire', 'Propriétaire'), ('demarcheur', 'Démarcheur / agent')]


class LogementQuerySet(models.QuerySet):
    def visibles(self):
        """Annonces visibles par le public : validées et pas encore louées."""
        return self.filter(statut='publie', loue=False)


class Logement(models.Model):
    type = models.CharField("Type", max_length=20, choices=TYPES, default='chambre_salon', db_index=True)
    titre = models.CharField("Titre court", max_length=120, blank=True,
                             help_text="Facultatif. Vide = « Type à Quartier ».")
    ville = models.CharField("Ville", max_length=80, default='Lomé', db_index=True)
    quartier = models.CharField("Quartier", max_length=120, db_index=True)
    repere = models.CharField("Repère / adresse", max_length=200, blank=True, help_text="Ex. près du marché, face à l'école…")
    latitude = models.DecimalField("Latitude", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("Longitude", max_digits=9, decimal_places=6, null=True, blank=True)
    loyer = models.PositiveIntegerField("Loyer (CFA)", db_index=True)
    periode = models.CharField("Période", max_length=6, choices=PERIODES, default='mois')
    caution = models.CharField("Caution / avance", max_length=120, blank=True, help_text="Ex. 3 mois d'avance + 1 mois de caution")
    pieces = models.PositiveSmallIntegerField("Nombre de pièces", null=True, blank=True)
    meuble = models.BooleanField("Meublé", default=False, db_index=True)
    compteur_eau = models.CharField("Eau", max_length=12, choices=COMPTEURS, blank=True)
    compteur_electricite = models.CharField("Électricité", max_length=12, choices=COMPTEURS, blank=True)
    equipements = models.JSONField("Équipements", default=list, blank=True)
    description = models.TextField("Description", blank=True)
    disponible_le = models.DateField("Disponible à partir du", null=True, blank=True)
    loue = models.BooleanField("Loué (masqué)", default=False, db_index=True)
    statut = models.CharField("Statut", max_length=8, choices=STATUTS, default='publie', db_index=True,
                              help_text="« En attente » et « Refusée » : jamais visible sur le site ni dans l'appli.")
    propose_par_role = models.CharField("Proposé par", max_length=12, choices=ROLES, blank=True)
    propose_le = models.DateTimeField("Proposé le", null=True, blank=True, editable=False)
    alias = models.CharField("Mots-clés", max_length=200, blank=True,
                             help_text="Autres noms du quartier, sigles… séparés par des virgules (recherche).")
    proprietaire_nom = models.CharField("Propriétaire (privé)", max_length=120, blank=True)
    proprietaire_telephone = models.CharField("Téléphone du propriétaire (privé)", max_length=40, blank=True,
                                              help_text="Jamais affiché : visible dans l'admin seulement.")
    ordre = models.PositiveSmallIntegerField("Ordre d'affichage", default=0)
    texte_recherche = models.TextField(blank=True, editable=False)
    vues = models.PositiveIntegerField("Vues", default=0, editable=False)
    contacts = models.PositiveIntegerField("Contacts (WhatsApp + appel)", default=0, editable=False)
    created_at = models.DateTimeField("Ajouté le", auto_now_add=True)

    objects = LogementQuerySet.as_manager()

    class Meta:
        ordering = ['ordre', '-created_at']
        verbose_name = "Annonce de location"
        verbose_name_plural = "Annonces de location"
        indexes = [models.Index(fields=['loue', 'ville', 'type'])]

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        # texte cherché : type en clair, lieu, repère, mots-clés (la recherche tolère accents, casse et fautes)
        self.texte_recherche = ' '.join(x for x in [self.get_type_display(), self.titre, self.quartier, self.ville,
                                                     self.repere, self.alias, 'meublé' if self.meuble else ''] if x)
        super().save(*args, **kwargs)

    @property
    def nom(self):
        return self.titre or f"{self.get_type_display()} à {self.quartier}"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('logements:detail', args=[self.pk])


class PhotoLogement(models.Model):
    logement = models.ForeignKey(Logement, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField("Photo", upload_to='logements/')
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['ordre', 'pk']
        verbose_name = "Photo"
        verbose_name_plural = "Photos"


class DemandeLogement(models.Model):
    """« Je cherche un logement » : la demande arrive dans l'admin et dans « À traiter »."""
    STATUTS = [('nouvelle', 'Nouvelle'), ('traitee', 'Traitée')]
    nom = models.CharField("Nom", max_length=120)
    telephone = models.CharField("WhatsApp", max_length=20, help_text="228XXXXXXXX")
    type = models.CharField("Type", max_length=20, choices=TYPES)
    lieu = models.CharField("Quartier ou ville", max_length=120)
    budget = models.PositiveIntegerField("Budget par mois (CFA)")
    date_souhaitee = models.DateField("Pour quand", null=True, blank=True)
    message = models.TextField("Message", blank=True)
    statut = models.CharField("Statut", max_length=10, choices=STATUTS, default='nouvelle', db_index=True)
    note = models.TextField("Note interne", blank=True)
    created_at = models.DateTimeField("Reçue le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Demande de logement"
        verbose_name_plural = "Demandes de logement"

    def __str__(self):
        return f"{self.nom} · {self.get_type_display()} à {self.lieu}"


class FicheLogement(models.Model):
    """Fiche par type de logement et quartier : « à partir de » un loyer relevé dans les annonces publiques ;
    le client écrit sur WhatsApp et Lantante cherche pour lui."""
    type_libelle = models.CharField("Type", max_length=60, help_text="Ex. Chambre salon, Studio meublé, Villa")
    quartier = models.CharField("Quartier", max_length=80)
    ville = models.CharField("Ville", max_length=60, default='Lomé')
    prix_min = models.PositiveIntegerField("À partir de (CFA / mois)")
    image = models.ImageField("Photo", upload_to='logements/fiches/')
    visible = models.BooleanField("Visible", default=True, db_index=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)
    sources = models.TextField("Sources des prix (interne)", blank=True)
    credit_photo = models.TextField("Crédit de la photo (interne)", blank=True)

    class Meta:
        ordering = ['ordre', 'prix_min']
        verbose_name = "Fiche de recherche"
        verbose_name_plural = "Fiches de recherche"

    def __str__(self):
        return f"{self.type_libelle} à {self.quartier}"

    @property
    def message(self):
        return f"Bonjour, je cherche : {self.type_libelle} à {self.quartier}"
