"""Lantante Express — « Commander une course » (phase 1).

Tout se gère dans l'admin et l'application mobile : rien sur le site public.
Les catégories, tarifs, plages horaires et paramètres sont des lignes en base (modifiables sans redéployer).
L'argent du client passe par Payments.solde (portefeuille Lantante) ; l'argent du partenaire par
MouvementSoldePartenaire (solde positif = Lantante lui doit, négatif = il doit à Lantante)."""
import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from Payments.models import private_storage
from Users.models import User


class Service(models.Model):
    CODES = [('moto', 'Moto'), ('tricycle', 'Tricycle'), ('voiture', 'Voiture'), ('cargo', 'Cargo')]
    code = models.CharField("Code", max_length=12, choices=CODES, unique=True)
    nom = models.CharField("Nom", max_length=60)
    actif = models.BooleanField("Actif", default=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = "Service"
        verbose_name_plural = "Services"

    def __str__(self):
        return self.nom


class Categorie(models.Model):
    VEHICULES = [('moto', 'Moto'), ('voiture', 'Voiture')]
    ICONES = [('moto', 'Moto'), ('tricycle', 'Tricycle'), ('voiture', 'Voiture standard'),
              ('voiture_clim', 'Voiture climatisée'), ('prestige', 'Prestige'), ('camionnette', 'Camionnette'),
              ('colis', 'Colis')]
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='categories', verbose_name="Service")
    nom = models.CharField("Nom", max_length=60)
    code = models.SlugField("Code", max_length=40, unique=True)
    vehicule = models.CharField("Véhicule", max_length=10, choices=VEHICULES, default='moto',
                                help_text="Sert aux frais d'annulation et au prix d'attente.")
    icone = models.CharField("Icône dans l'appli", max_length=12, choices=ICONES, blank=True,
                             help_text="Petite image affichée dans l'appli. Vide : choisie d'après le service.")
    active = models.BooleanField("Active", default=True, help_text="Inactive : affichée « Bientôt » dans l'appli.")
    capacite = models.PositiveSmallIntegerField("Capacité (passagers)", default=1)
    poids_max = models.PositiveIntegerField("Poids max (kg)", null=True, blank=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)
    prise_en_charge = models.PositiveIntegerField("Prise en charge (FCFA)", default=0)
    prix_km = models.PositiveIntegerField("Prix par km (FCFA)", default=0)
    prix_min = models.PositiveIntegerField("Prix par minute (FCFA)", default=0)
    minimum = models.PositiveIntegerField(
        "Tarif de base (FCFA)", default=0,
        help_text="Prix minimum d'une course : même pour quelques mètres, le client paie au moins ce montant.")
    commission_pct = models.DecimalField("Commission (%)", max_digits=5, decimal_places=2, default=15,
                                         validators=[MinValueValidator(0), MaxValueValidator(100)])
    code_depart_obligatoire = models.BooleanField("Code de départ obligatoire", default=False,
                                                  help_text="Exige le code pour cette catégorie, même si le réglage "
                                                            "général est désactivé.")

    class Meta:
        ordering = ['service__ordre', 'ordre', 'id']
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories et tarifs"

    def __str__(self):
        return f"{self.service.nom} — {self.nom}"


class PlageHoraire(models.Model):
    nom = models.CharField("Nom", max_length=40)
    debut = models.TimeField("Début")
    fin = models.TimeField("Fin", help_text="Si la fin est avant le début, la plage passe minuit (ex. 23 h – 6 h).")
    coefficient = models.DecimalField("Coefficient", max_digits=4, decimal_places=2, default=1)

    class Meta:
        ordering = ['debut']
        verbose_name = "Plage horaire"
        verbose_name_plural = "Plages horaires"

    def __str__(self):
        return f"{self.nom} ({self.debut:%H:%M}–{self.fin:%H:%M}) × {self.coefficient}"

    def contient(self, t):
        if self.debut <= self.fin:
            return self.debut <= t < self.fin
        return t >= self.debut or t < self.fin


MESSAGE_ACCEPTATION_ANCIEN = ("Bonjour {prenom_client}, votre demande de course a été acceptée. Le coursier {prenom_coursier} "
                              "({vehicule}, {plaque}) est en route et sera bientôt là, environ {eta} min. Merci d'être prêt.")
MESSAGE_ACCEPTATION_V2 = ("✅ Course acceptée !\n\n"
                          "Bonjour {prenom_client} 👋\n"
                          "{prenom_coursier} arrive dans environ {eta} min.\n\n"
                          "{emoji} {vehicule}\n"
                          "🔖 Plaque : {plaque}\n\n"
                          "Merci d'être prêt au point de départ. Bonne route avec Lantante Express !")
MESSAGE_ACCEPTATION_V3 = ("Bonjour {prenom_client},\n\n"
                       "Votre course est acceptée. {prenom_coursier} arrive dans environ {eta} min.\n\n"
                       "Véhicule : {vehicule}\n"
                       "Plaque : {plaque}\n\n"
                       "Merci d'être prêt au point de départ.\n"
                       "Lantante Express")
MESSAGE_ACCEPTATION = ("Bonjour {prenom_client},\n\n"
                       "Votre coursier {nom_coursier} est en route. Il arrive dans environ {eta} min.\n\n"
                       "Véhicule : {vehicule}\n"
                       "Plaque : {plaque}\n\n"
                       "Merci d'être prêt au point de départ.\n"
                       "Lantante Express")
MENTION_PRIX_V1 = ("Ce prix peut augmenter si le trajet change (autre destination, arrêt), en cas d'attente "
                   "au-delà de {attente} min, ou si le trajet réel est nettement plus long que prévu.")
MENTION_PRIX = ("Prix estimé. Le prix exact est compté au compteur, du départ à l'arrivée "
                "(km et minutes réels), avec le tarif de base au minimum.")
MESSAGE_ARRIVEE_ANCIEN = "Votre coursier {prenom_coursier} est arrivé ({vehicule}, {plaque})."
MESSAGE_ARRIVEE_V2 = ("📍 Votre coursier est arrivé !\n\n"
                      "{prenom_coursier} vous attend.\n"
                      "{emoji} {vehicule}\n"
                      "🔖 Plaque : {plaque}\n\n"
                      "⏱️ Attente gratuite : {attente} min. À tout de suite !")
MESSAGE_ARRIVEE_V3 = ("Votre coursier {prenom_coursier} est arrivé.\n\n"
                   "Véhicule : {vehicule}\n"
                   "Plaque : {plaque}\n\n"
                   "Attente gratuite : {attente} min. Au-delà, l'attente est facturée.\n"
                   "Lantante Express")
MESSAGE_ARRIVEE = ("Votre coursier {nom_coursier} est arrivé.\n\n"
                   "Véhicule : {vehicule}\n"
                   "Plaque : {plaque}\n\n"
                   "Attente gratuite : {attente} min. Au-delà, l'attente est facturée.\n"
                   "Lantante Express")
MESSAGE_FIN_V1 = ("🎉 Course terminée !\n\n"
                  "Merci beaucoup {prenom_client} de nous avoir choisis 💚\n"
                  "Nous espérons que tout s'est bien passé avec {prenom_coursier}.\n\n"
                  "À très bientôt sur Lantante Express !")
MESSAGE_FIN = ("Course terminée.\n\n"
               "Merci {prenom_client} de nous avoir choisis. "
               "Votre reçu est disponible dans l'application.\n\n"
               "À très bientôt,\n"
               "Lantante Express")
MESSAGE_AUCUN = ("Aucun coursier disponible dans votre zone pour le moment. "
                 "Merci de réessayer dans quelques instants.")


class Parametres(models.Model):
    """Réglages de Lantante Express (une seule ligne)."""
    # Affectation
    rayon_initial_km = models.DecimalField("Rayon initial (km)", max_digits=5, decimal_places=2, default=3)
    palier_1_km = models.DecimalField("1er élargissement (km)", max_digits=5, decimal_places=2, default=5)
    palier_2_km = models.DecimalField("2e élargissement (km)", max_digits=5, decimal_places=2, default=8)
    delai_reponse_s = models.PositiveSmallIntegerField("Délai de réponse (s)", default=10)
    delai_accuse_s = models.PositiveSmallIntegerField("Délai d'accusé de réception (s)", default=3)
    age_gps_max_s = models.PositiveSmallIntegerField("Âge max de la position GPS (s)", default=30)
    offres_max = models.PositiveSmallIntegerField("Offres max par course", default=8)
    recherche_max_s = models.PositiveSmallIntegerField("Durée max de recherche (s)", default=120)
    offres_ignorees_max = models.PositiveSmallIntegerField("Offres ignorées avant passage hors ligne", default=3)
    # Annulation et attente
    delai_grace_min = models.PositiveSmallIntegerField("Délai de grâce annulation (min)", default=2)
    frais_annulation_moto = models.PositiveIntegerField("Frais d'annulation moto (FCFA)", default=200)
    frais_annulation_voiture = models.PositiveIntegerField("Frais d'annulation voiture (FCFA)", default=200)
    attente_absent_min = models.PositiveSmallIntegerField("Attente avant « client absent » (min)", default=5)
    frais_absent_moto = models.PositiveIntegerField("Frais client absent moto (FCFA)", default=200)
    frais_absent_voiture = models.PositiveIntegerField("Frais client absent voiture (FCFA)", default=200)
    retard_exonerant_min = models.PositiveSmallIntegerField("Retard du partenaire qui exonère le client (min)", default=5)
    attente_gratuite_min = models.PositiveSmallIntegerField(
        "Attente gratuite (min)", default=2,
        help_text="Après l'arrivée du coursier, le client a ces minutes gratuites ; ensuite l'attente est facturée.")
    rayon_arrivee_auto_m = models.PositiveSmallIntegerField(
        "Arrivée automatique (m)", default=40,
        help_text="Le système marque « Coursier arrivé » tout seul quand il est à moins de cette distance du départ.")
    rayon_arrivee_manuelle_m = models.PositiveSmallIntegerField(
        "Bouton « Je suis arrivé » (m)", default=150,
        help_text="Le coursier ne peut dire « Je suis arrivé » que s'il est à moins de cette distance du départ.")
    pourboire_max = models.PositiveIntegerField("Pourboire maximum (FCFA)", default=500)
    prix_attente_moto = models.PositiveIntegerField("Prix de l'attente moto (FCFA/min)", default=100)
    prix_attente_voiture = models.PositiveIntegerField("Prix de l'attente voiture (FCFA/min)", default=200)
    # Prix
    arrondi = models.PositiveIntegerField("Arrondi (FCFA)", default=50)
    vitesse_moyenne_kmh = models.PositiveSmallIntegerField("Vitesse moyenne estimée (km/h)", default=25)
    coef_route = models.DecimalField("Coefficient route / vol d'oiseau", max_digits=4, decimal_places=2, default=1.3)
    seuil_augmentation_pct = models.PositiveSmallIntegerField(
        "Seuil d'augmentation (%)", default=15,
        help_text="Si la distance réelle dépasse la distance prévue de plus de ce pourcentage, le prix est recalculé "
                  "sur la distance réelle (jamais en dessous du prix annoncé).")
    message_zone = models.CharField("Message hors zone", max_length=200, default="Zone non couverte")
    message_aucun_partenaire = models.CharField("Message « aucun coursier »", max_length=255, default=MESSAGE_AUCUN)
    code_depart_obligatoire = models.BooleanField(
        "Code de départ obligatoire", default=False,
        help_text="Désactivé : le coursier démarre avec un simple bouton et le client ne voit pas de code. "
                  "Peut aussi être exigé pour une seule catégorie (fiche de la catégorie).")
    favoris_prioritaires = models.BooleanField(
        "Coursiers favoris servis en premier", default=True,
        help_text="Les coursiers favoris du client reçoivent l'offre avant les autres (par distance).")
    rayon_favoris_km = models.DecimalField("Rayon max pour un favori (km)", max_digits=5, decimal_places=2, default=8)
    rayon_proches_km = models.DecimalField("Coursiers affichés sur la carte : rayon (km)", max_digits=5,
                                           decimal_places=2, default=5)
    mention_prix = models.TextField("Mention sous le prix", default=MENTION_PRIX,
                                    help_text="Variable : {attente} = minutes d'attente gratuite.")
    # Dette des partenaires
    dette_max_especes = models.PositiveIntegerField("Dette max avant blocage des courses en espèces (FCFA)", default=10000)
    dette_max_totale = models.PositiveIntegerField("Dette max avant blocage total (FCFA)", default=15000)
    retrait_frais_pct = models.DecimalField(
        "Frais de retrait client (%)", max_digits=5, decimal_places=2, default=0,
        help_text="Payés par le client : retenus sur le montant qu'il retire.")
    retrait_frais_min = models.PositiveIntegerField("Frais de retrait minimum (FCFA)", default=0)
    alerte_solde = models.PositiveIntegerField(
        "Alerte solde négatif (FCFA)", default=5000,
        help_text="Quand le solde d'un coursier descend sous −ce montant : message « Rechargez votre compte » "
                  "au coursier et alerte à l'équipe.")
    # Remboursement
    plafond_remboursement = models.PositiveIntegerField("Remboursement max sans second admin (FCFA)", default=5000)
    versement_min = models.PositiveIntegerField("Versement : montant minimum (FCFA)", default=2000)
    # Fidélité
    fidelite_courses = models.PositiveSmallIntegerField("Fidélité : courses requises", default=10)
    fidelite_pct = models.PositiveSmallIntegerField("Fidélité : réduction (%)", default=10)
    fidelite_plafond = models.PositiveIntegerField("Fidélité : plafond (FCFA)", default=1000)
    fidelite_validite_jours = models.PositiveSmallIntegerField("Fidélité : validité (jours)", default=30)
    # Notes
    note_avertissement = models.DecimalField("Note : seuil d'avertissement", max_digits=3, decimal_places=2, default=4.2)
    note_suspension = models.DecimalField("Note : seuil de suspension", max_digits=3, decimal_places=2, default=4.0)
    notes_min_affichage = models.PositiveSmallIntegerField("Notes minimum avant affichage", default=5)
    # Discussion client ↔ partenaire
    chat_ouvert_apres_fin_min = models.PositiveSmallIntegerField(
        "Discussion ouverte après la fin (min)", default=0,
        help_text="0 : la discussion s'arrête dès la fin de la course (l'historique reste visible).")
    audio_duree_max_s = models.PositiveSmallIntegerField("Message vocal : durée max (s)", default=60)
    fichier_taille_max_ko = models.PositiveIntegerField("Message vocal ou photo : taille max (Ko)", default=5120)
    modele_message_acceptation = models.TextField(
        "Message automatique à l'acceptation", default=MESSAGE_ACCEPTATION,
        help_text="Variables : {prenom_client}, {prenom_coursier}, {nom_coursier} (nom complet), {vehicule} (marque, modèle, couleur), {plaque}, "
                  "{eta} (minutes), {code}, {emoji} (🏍️ 🛺 🚗), {attente} (minutes gratuites).")
    modele_message_fin = models.TextField(
        "Message automatique à la fin (remerciement)", default=MESSAGE_FIN,
        help_text="Mêmes variables que le message d'acceptation.")
    modele_message_arrivee = models.TextField(
        "Message automatique à l'arrivée", default=MESSAGE_ARRIVEE,
        help_text="Mêmes variables que le message d'acceptation.")

    class Meta:
        verbose_name = "Paramètres"
        verbose_name_plural = "Paramètres"

    def __str__(self):
        return "Paramètres de Lantante Express"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # pragma: no cover - singleton
        return None

    @classmethod
    def get(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def paliers(self):
        return [float(self.rayon_initial_km), float(self.palier_1_km), float(self.palier_2_km)]


class Partenaire(models.Model):
    TYPES = [('coursier', 'Coursier'), ('livreur', 'Livreur'), ('mixte', 'Coursier et livreur')]
    STATUTS = [('a_completer', 'Profil à compléter'), ('en_attente', 'En attente de validation'), ('valide', 'Validé'),
               ('refuse', 'Refusé'), ('suspendu', 'Suspendu')]
    VEHICULES = [('moto', 'Moto'), ('tricycle', 'Tricycle'), ('voiture', 'Voiture')]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='partenaire_express',
                                verbose_name="Compte")
    type = models.CharField("Type", max_length=10, choices=TYPES, default='coursier')
    statut = models.CharField("Vérification", max_length=12, choices=STATUTS, default='en_attente')
    motif_statut = models.CharField("Motif (refus, suspension)", max_length=255, blank=True)
    en_ligne = models.BooleanField("En ligne", default=False)
    lat = models.FloatField("Latitude", null=True, blank=True)
    lng = models.FloatField("Longitude", null=True, blank=True)
    position_le = models.DateTimeField("Position reçue le", null=True, blank=True)
    categories = models.ManyToManyField(Categorie, blank=True, related_name='partenaires', verbose_name="Catégories servies")
    type_vehicule = models.CharField("Type de véhicule", max_length=10, choices=VEHICULES, blank=True,
                                     help_text="Un seul type par coursier. Changer = nouvelle demande validée par l'admin.")
    climatise = models.BooleanField("Voiture climatisée", default=False)
    marque = models.CharField("Marque", max_length=40, blank=True)
    modele = models.CharField("Modèle", max_length=40, blank=True)
    couleur = models.CharField("Couleur", max_length=30, blank=True)
    annee = models.PositiveSmallIntegerField("Année", null=True, blank=True)
    date_naissance = models.DateField("Date de naissance", null=True, blank=True)
    quartier = models.CharField("Quartier / adresse", max_length=120, blank=True)
    urgence_nom = models.CharField("Contact d'urgence : nom", max_length=80, blank=True)
    urgence_tel = models.CharField("Contact d'urgence : téléphone", max_length=20, blank=True)
    vehicule = models.CharField("Véhicule", max_length=80, blank=True, help_text="Marque, modèle, couleur.")
    plaque = models.CharField("Plaque", max_length=20, blank=True)
    telephone = models.CharField("Téléphone", max_length=20, blank=True)
    mobile_money = models.CharField("Numéro Mobile Money (versements)", max_length=20, blank=True)
    note = models.DecimalField("Note", max_digits=3, decimal_places=2, default=5)
    nb_notes = models.PositiveIntegerField("Nombre de notes", default=0)
    solde = models.IntegerField("Solde (FCFA)", default=0, editable=False,
                                help_text="Positif : Lantante lui doit. Négatif : il doit à Lantante.")
    offres_ignorees = models.PositiveSmallIntegerField("Offres ignorées d'affilée", default=0)
    avertissements = models.PositiveIntegerField("Avertissements", default=0)
    created_at = models.DateTimeField("Inscrit le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Partenaire"
        verbose_name_plural = "Partenaires (coursiers et livreurs)"
        indexes = [models.Index(fields=['en_ligne', 'statut', 'lat', 'lng'])]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} ({self.get_type_display()})"

    @property
    def dette(self):
        return max(0, -self.solde)


class DocumentPartenaire(models.Model):
    TYPES = [('selfie', 'Photo de profil'), ('identite_recto', "Carte d'identité (recto)"),
             ('identite_verso', "Carte d'identité (verso)"), ('permis_recto', 'Permis (recto)'),
             ('permis_verso', 'Permis (verso)'), ('carte_grise', 'Carte grise'), ('assurance', 'Assurance'),
             ('photo_avant', 'Véhicule : avant'), ('photo_arriere', 'Véhicule : arrière avec plaque'),
             ('photo_cote', 'Véhicule : côté'), ('photo_interieur', 'Véhicule : intérieur'),
             ('casier', 'Casier judiciaire'),
             ('identite', "Carte d'identité ou passeport"), ('permis', 'Permis de conduire'),
             ('photo_vehicule', 'Photo du véhicule'), ('autre', 'Autre')]
    STATUTS = [('en_attente', 'En attente'), ('valide', 'Validé'), ('refuse', 'Refusé')]
    partenaire = models.ForeignKey(Partenaire, on_delete=models.CASCADE, related_name='documents')
    type = models.CharField("Type", max_length=16, choices=TYPES)
    fichier = models.FileField("Fichier", upload_to='courses/documents/', storage=private_storage)
    expiration = models.DateField("Expire le", null=True, blank=True)
    statut = models.CharField("Statut", max_length=12, choices=STATUTS, default='en_attente')
    motif = models.CharField("Motif du refus", max_length=255, blank=True)
    created_at = models.DateTimeField("Envoyé le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Document du partenaire"
        verbose_name_plural = "Documents des partenaires"

    def __str__(self):
        return f"{self.get_type_display()} — {self.partenaire}"


class DemandeChangementType(models.Model):
    STATUTS = [('en_attente', 'En attente'), ('valide', 'Validée'), ('refuse', 'Refusée')]
    partenaire = models.ForeignKey(Partenaire, on_delete=models.CASCADE, related_name='demandes_type')
    type_actuel = models.CharField("Type actuel", max_length=10, choices=Partenaire.TYPES)
    type_demande = models.CharField("Type demandé", max_length=10, choices=Partenaire.TYPES)
    vehicule_demande = models.CharField("Véhicule demandé", max_length=10, choices=Partenaire.VEHICULES, blank=True)
    motif = models.CharField("Motif", max_length=255, blank=True)
    statut = models.CharField("Statut", max_length=12, choices=STATUTS, default='en_attente')
    traite_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name="Traitée par")
    traite_le = models.DateTimeField("Traitée le", null=True, blank=True)
    created_at = models.DateTimeField("Demandée le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Demande de changement de type"
        verbose_name_plural = "Demandes de changement de type"

    def __str__(self):
        return f"{self.partenaire} : {self.get_type_actuel_display()} → {self.get_type_demande_display()}"


def code_depart():
    return f"{secrets.randbelow(10000):04d}"


ALPHABET_REF = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # sans 0/O/1/I


def nouvelle_reference():
    return 'LX-' + ''.join(secrets.choice(ALPHABET_REF) for _ in range(6))


class Course(models.Model):
    STATUTS = [('recherche', 'Recherche'), ('acceptee', 'Acceptée'), ('arrive', 'Coursier arrivé'),
               ('en_cours', 'En cours'), ('terminee', 'Terminée'), ('annulee', 'Annulée'),
               ('aucun_partenaire', 'Aucun coursier'), ('litige', 'Litige')]
    ACTIFS = ('recherche', 'acceptee', 'arrive', 'en_cours')
    MOYENS = [('especes', 'Espèces'), ('portefeuille', 'Solde Lantante')]
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='courses_express',
                               verbose_name="Client")
    categorie = models.ForeignKey(Categorie, on_delete=models.PROTECT, related_name='courses', verbose_name="Catégorie")
    depart_lat = models.FloatField("Départ lat")
    depart_lng = models.FloatField("Départ lng")
    depart_adresse = models.CharField("Départ", max_length=255, blank=True)
    repere = models.CharField("Point de repère", max_length=255, blank=True)
    arrivee_lat = models.FloatField("Arrivée lat")
    arrivee_lng = models.FloatField("Arrivée lng")
    arrivee_adresse = models.CharField("Arrivée", max_length=255, blank=True)
    distance_km = models.DecimalField("Distance (km)", max_digits=7, decimal_places=2)
    duree_min = models.PositiveIntegerField("Durée estimée (min)")
    prix_estime = models.PositiveIntegerField("Prix estimé (FCFA)", help_text="Avant réduction.")
    prix_final = models.PositiveIntegerField("Prix final (FCFA)", null=True, blank=True, help_text="Avant réduction.")
    promo = models.ForeignKey('PromoCourse', on_delete=models.SET_NULL, null=True, blank=True, related_name='courses',
                              verbose_name="Promotion")
    reduction = models.PositiveIntegerField("Réduction (FCFA)", default=0)
    frais_impayes = models.PositiveIntegerField("Frais d'annulation reportés (FCFA)", default=0)
    detail_prix = models.JSONField("Détail du prix", default=dict, blank=True)
    moyen_paiement = models.CharField("Paiement", max_length=12, choices=MOYENS, default='especes')
    montant_reserve = models.PositiveIntegerField("Montant réservé sur le solde (FCFA)", default=0)
    statut = models.CharField("Statut", max_length=16, choices=STATUTS, default='recherche', db_index=True)
    code_depart = models.CharField("Code de départ", max_length=4, default=code_depart)
    reference = models.CharField("Référence", max_length=12, unique=True, default=nouvelle_reference,
                                 help_text="Code unique de la course (ex. LX-7K3Q9A).")
    partenaire = models.ForeignKey(Partenaire, on_delete=models.PROTECT, null=True, blank=True, related_name='courses',
                                   verbose_name="Partenaire")
    rayon_km = models.DecimalField("Rayon de recherche (km)", max_digits=5, decimal_places=2, default=0)
    distance_reelle_km = models.DecimalField("Distance réelle (km)", max_digits=7, decimal_places=2, default=0,
                                             help_text="Cumul des positions GPS du partenaire pendant la course.")
    derniere_lat = models.FloatField(null=True, blank=True, editable=False)
    derniere_lng = models.FloatField(null=True, blank=True, editable=False)
    recherche_debut = models.DateTimeField("Recherche commencée le", null=True, blank=True)
    acceptee_le = models.DateTimeField("Acceptée le", null=True, blank=True)
    arrivee_prevue_le = models.DateTimeField("Arrivée prévue du partenaire", null=True, blank=True)
    arrive_le = models.DateTimeField("Partenaire arrivé le", null=True, blank=True)
    demarree_le = models.DateTimeField("Démarrée le", null=True, blank=True)
    terminee_le = models.DateTimeField("Terminée le", null=True, blank=True)
    annulee_le = models.DateTimeField("Annulée le", null=True, blank=True)
    numero_recu = models.CharField("N° de reçu", max_length=20, blank=True, db_index=True)
    created_at = models.DateTimeField("Commandée le", auto_now_add=True)
    updated_at = models.DateTimeField("Mise à jour", auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Course"
        verbose_name_plural = "Courses"

    def __str__(self):
        return f"{self.reference} — {self.categorie.nom} — {self.get_statut_display()}"

    @property
    def total_client(self):
        """Ce que paie le client : prix (final sinon estimé) − réduction + frais reportés."""
        prix = self.prix_final if self.prix_final is not None else self.prix_estime
        return max(0, prix - self.reduction) + self.frais_impayes

    @property
    def active(self):
        return self.statut in self.ACTIFS

    @property
    def code_requis(self):
        return self.categorie.code_depart_obligatoire or Parametres.get().code_depart_obligatoire


class OffreCourse(models.Model):
    REPONSES = [('en_attente', 'En attente'), ('acceptee', 'Acceptée'), ('refusee', 'Refusée'),
                ('ignoree', 'Ignorée'), ('expiree', 'Expirée'), ('annulee', 'Annulée ensuite')]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='offres')
    partenaire = models.ForeignKey(Partenaire, on_delete=models.CASCADE, related_name='offres')
    distance_km = models.DecimalField("Distance jusqu'au départ (km)", max_digits=7, decimal_places=2)
    envoyee_le = models.DateTimeField("Envoyée le", default=timezone.now)
    recue_le = models.DateTimeField("Reçue le", null=True, blank=True)
    expire_le = models.DateTimeField("Expire le")
    reponse = models.CharField("Réponse", max_length=12, choices=REPONSES, default='en_attente', db_index=True)
    repondue_le = models.DateTimeField("Répondue le", null=True, blank=True)

    class Meta:
        ordering = ['envoyee_le', 'id']
        verbose_name = "Offre"
        verbose_name_plural = "Offres envoyées"

    def __str__(self):
        return f"Offre course {self.course_id} → {self.partenaire} ({self.get_reponse_display()})"


class Annulation(models.Model):
    PAR = [('client', 'Client'), ('partenaire', 'Partenaire'), ('admin', 'Admin'), ('systeme', 'Système')]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='annulations')
    par = models.CharField("Annulée par", max_length=10, choices=PAR)
    partenaire = models.ForeignKey(Partenaire, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
                                   verbose_name="Partenaire concerné")
    motif = models.CharField("Motif", max_length=255, blank=True)
    frais = models.PositiveIntegerField("Frais (FCFA)", default=0)
    frais_regles = models.BooleanField("Frais réglés", default=True)
    created_at = models.DateTimeField("Le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Annulation"
        verbose_name_plural = "Annulations"

    def __str__(self):
        return f"Course {self.course_id} annulée par {self.get_par_display()}"


class Note(models.Model):
    AUTEURS = [('client', 'Le client note le partenaire'), ('partenaire', 'Le partenaire note le client')]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='notes')
    auteur = models.CharField("Sens", max_length=10, choices=AUTEURS)
    note = models.PositiveSmallIntegerField("Note", validators=[MinValueValidator(1), MaxValueValidator(5)])
    motifs = models.JSONField("Motifs", default=list, blank=True)
    commentaire = models.CharField("Commentaire", max_length=500, blank=True)
    created_at = models.DateTimeField("Le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Note"
        verbose_name_plural = "Notes"
        constraints = [models.UniqueConstraint(fields=['course', 'auteur'], name='une_note_par_sens')]

    def __str__(self):
        return f"{self.note}/5 — course {self.course_id}"


class Signalement(models.Model):
    MOTIFS = [('comportement', 'Comportement inapproprié'), ('conduite', 'Conduite dangereuse'),
              ('surfacturation', 'Prix non respecté'), ('retard', 'Retard important'), ('objet_oublie', 'Objet oublié'),
              ('colis', 'Colis abîmé ou perdu'), ('harcelement', 'Harcèlement'), ('agression', 'Agression'),
              ('autre', 'Autre')]
    GRAVES = ('agression', 'harcelement')
    STATUTS = [('nouveau', 'Nouveau'), ('en_cours', 'En cours'), ('resolu', 'Résolu'), ('rejete', 'Rejeté')]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='signalements')
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+', verbose_name="Auteur")
    par = models.CharField("Envoyé par", max_length=10, choices=[('client', 'Client'), ('partenaire', 'Partenaire')])
    motif = models.CharField("Motif", max_length=16, choices=MOTIFS)
    commentaire = models.TextField("Commentaire", max_length=2000, blank=True)
    piece_jointe = models.FileField("Pièce jointe", upload_to='courses/signalements/', storage=private_storage,
                                    blank=True)
    statut = models.CharField("Statut", max_length=10, choices=STATUTS, default='nouveau')
    reponse = models.TextField("Réponse au client", blank=True)
    created_at = models.DateTimeField("Le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Signalement"
        verbose_name_plural = "Signalements"

    def __str__(self):
        return f"{self.get_motif_display()} — course {self.course_id}"


class MouvementSoldePartenaire(models.Model):
    TYPES = [('commission', 'Commission'), ('gain', 'Gain'), ('frais_annulation', "Frais d'annulation reçus"),
             ('remboursement', 'Remboursement retenu'), ('versement', 'Versement'), ('reglement', 'Règlement de dette'),
             ('ajustement', 'Ajustement'), ('pourboire', 'Pourboire')]
    partenaire = models.ForeignKey(Partenaire, on_delete=models.PROTECT, related_name='mouvements')
    type = models.CharField("Type", max_length=16, choices=TYPES)
    montant = models.IntegerField("Montant (FCFA)", help_text="Positif : en faveur du partenaire.")
    solde_apres = models.IntegerField("Solde après")
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='mouvements_partenaire')
    motif = models.CharField("Motif", max_length=255, blank=True)
    par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='+', verbose_name="Fait par")
    created_at = models.DateTimeField("Le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = "Mouvement du solde partenaire"
        verbose_name_plural = "Mouvements des soldes partenaires"

    def __str__(self):
        return f"{self.get_type_display()} {self.montant:+} FCFA"


class Remboursement(models.Model):
    STATUTS = [('en_attente', 'En attente d\'un second admin'), ('valide', 'Validé')]
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='remboursements')
    montant = models.PositiveIntegerField("Montant remboursé au client (FCFA)")
    part_partenaire = models.PositiveIntegerField("Part retenue au partenaire (FCFA)", default=0)
    part_lantante = models.PositiveIntegerField("Part prise par Lantante (FCFA)", default=0)
    motif = models.CharField("Motif", max_length=255)
    statut = models.CharField("Statut", max_length=12, choices=STATUTS, default='en_attente')
    demande_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+', verbose_name="Demandé par")
    valide_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name="Validé par")
    valide_le = models.DateTimeField("Validé le", null=True, blank=True)
    created_at = models.DateTimeField("Le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Remboursement"
        verbose_name_plural = "Remboursements"

    def __str__(self):
        return f"Remboursement {self.montant} FCFA — course {self.course_id}"


class CompteurRecu(models.Model):
    """Numérotation unique et continue des reçus : LE-AAAA-NNNNNN."""
    annee = models.PositiveSmallIntegerField(primary_key=True)
    dernier = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Compteur de reçus"
        verbose_name_plural = "Compteurs de reçus"


class MessageCourse(models.Model):
    """Discussion liée à une course : client et partenaire seulement, de l'acceptation à 1 h après la fin,
    puis lecture seule (visible dans l'admin en cas de litige)."""
    TYPES = [('texte', 'Texte'), ('audio', 'Message vocal'), ('image', 'Photo'), ('position', 'Position'),
             ('systeme', 'Message automatique')]
    PAR = [('client', 'Client'), ('partenaire', 'Partenaire'), ('systeme', 'Lantante Express')]
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='messages')
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='+', verbose_name="Auteur")
    par = models.CharField("Envoyé par", max_length=10, choices=PAR)
    type = models.CharField("Type", max_length=10, choices=TYPES, default='texte')
    texte = models.TextField("Texte", max_length=1000, blank=True)
    fichier = models.FileField("Fichier", upload_to='courses/discussions/', storage=private_storage, blank=True)
    duree_audio_s = models.PositiveSmallIntegerField("Durée du vocal (s)", null=True, blank=True)
    lat = models.FloatField("Latitude", null=True, blank=True)
    lng = models.FloatField("Longitude", null=True, blank=True)
    lu_le = models.DateTimeField("Lu le", null=True, blank=True)
    created_at = models.DateTimeField("Envoyé le", auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name = "Message"
        verbose_name_plural = "Discussions des courses"
        indexes = [models.Index(fields=['course', 'id'])]

    def __str__(self):
        return f"{self.get_par_display()} — course {self.course_id} — {self.get_type_display()}"


class DemandeVersement(models.Model):
    """Le partenaire demande le versement de son solde positif sur son numéro Mobile Money ;
    l'équipe paie puis marque la demande « Payée » (le solde est débité à ce moment-là)."""
    STATUTS = [('en_attente', 'En attente'), ('paye', 'Payée'), ('refuse', 'Refusée')]
    partenaire = models.ForeignKey(Partenaire, on_delete=models.PROTECT, related_name='versements')
    montant = models.PositiveIntegerField("Montant (FCFA)")
    numero = models.CharField("Numéro Mobile Money", max_length=20)
    statut = models.CharField("Statut", max_length=12, choices=STATUTS, default='en_attente')
    motif = models.CharField("Motif du refus", max_length=255, blank=True)
    traite_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+', verbose_name="Traitée par")
    traite_le = models.DateTimeField("Traitée le", null=True, blank=True)
    created_at = models.DateTimeField("Demandée le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Demande de versement"
        verbose_name_plural = "Demandes de versement"

    def __str__(self):
        return f"{self.montant} FCFA — {self.partenaire}"


class Zone(models.Model):
    """Zone couverte (centre + rayon). Sans zone active : partout. Départ ET arrivée doivent être dans une zone."""
    nom = models.CharField("Nom", max_length=80)
    centre_lat = models.FloatField("Centre : latitude")
    centre_lng = models.FloatField("Centre : longitude")
    rayon_km = models.DecimalField("Rayon (km)", max_digits=6, decimal_places=2, default=25)
    active = models.BooleanField("Active", default=True)

    class Meta:
        ordering = ['nom']
        verbose_name = "Zone couverte"
        verbose_name_plural = "Zones couvertes"

    def __str__(self):
        return f"{self.nom} ({self.rayon_km} km)"


class PinSolde(models.Model):
    """Code PIN du solde : seulement des empreintes (jamais le code), essais et blocage."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pin_solde',
                                verbose_name="Utilisateur")
    pin_hash = models.CharField(max_length=128, blank=True, editable=False)
    essais = models.PositiveSmallIntegerField("Essais faux", default=0)
    bloque_jusqua = models.DateTimeField("Bloqué jusqu'à", null=True, blank=True)
    code_hash = models.CharField(max_length=128, blank=True, editable=False)
    code_envoye_le = models.DateTimeField(null=True, blank=True, editable=False)
    updated_at = models.DateTimeField("Modifié le", auto_now=True)

    class Meta:
        verbose_name = "Code PIN du solde"
        verbose_name_plural = "Codes PIN du solde"

    def __str__(self):
        return f"PIN de {self.user}"

    @property
    def defini(self):
        return bool(self.pin_hash)


class CoursierFavori(models.Model):
    """Coursier mis en favori par un client : il reçoit l'offre en premier s'il est disponible."""
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coursiers_favoris')
    partenaire = models.ForeignKey(Partenaire, on_delete=models.CASCADE, related_name='favori_de')
    created_at = models.DateTimeField("Ajouté le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Coursier favori"
        verbose_name_plural = "Coursiers favoris"
        constraints = [models.UniqueConstraint(fields=['client', 'partenaire'], name='un_favori_par_couple')]

    def __str__(self):
        return f"{self.partenaire} ← {self.client}"



# ─────────────────────────────
# Comptes vus par catégorie dans l'admin : UNE seule table de comptes (Users.User), plusieurs vues.
# Une même personne peut être cliente ET coursier avec le même e-mail.
# ─────────────────────────────
class _Comptes(models.Manager):
    filtre = {}
    exclure = {}

    def get_queryset(self):
        qs = super().get_queryset().filter(**self.filtre)
        for k, v in self.exclure.items():
            qs = qs.exclude(**{k: v})
        return qs.distinct()


# Catégories séparées, sans mélange : un compte n'apparaît que dans UNE liste.
# Système d'abord (équipe), puis coursier, puis vendeur ; tous les autres sont des clients.
class _Clients(_Comptes):
    filtre = {'is_staff': False, 'partenaire_express__isnull': True, 'vendeur__isnull': True}


class _Coursiers(_Comptes):
    filtre = {'is_staff': False, 'partenaire_express__isnull': False}


class _Systeme(_Comptes):
    filtre = {'is_staff': True}


class _Vendeurs(_Comptes):
    filtre = {'is_staff': False, 'vendeur__isnull': False}
    exclure = {'partenaire_express__isnull': False}


class CompteClient(User):
    objects = _Clients()

    class Meta:
        proxy = True
        verbose_name = "Client"
        verbose_name_plural = "Clients"


class CompteCoursier(User):
    objects = _Coursiers()

    class Meta:
        proxy = True
        verbose_name = "Coursier (compte)"
        verbose_name_plural = "Coursiers (comptes)"


class CompteSysteme(User):
    objects = _Systeme()

    class Meta:
        proxy = True
        verbose_name = "Utilisateur du système"
        verbose_name_plural = "Utilisateurs du système"


class CompteVendeur(User):
    objects = _Vendeurs()

    class Meta:
        proxy = True
        verbose_name = "Vendeur (compte)"
        verbose_name_plural = "Vendeurs (comptes)"



class MessageSupport(models.Model):
    """Messagerie entre l'équipe Lantante (support) et un coursier : question, demande d'explication, réponse."""
    PAR = [('support', 'Support Lantante'), ('coursier', 'Coursier')]
    partenaire = models.ForeignKey(Partenaire, on_delete=models.CASCADE, related_name='messages_support',
                                   verbose_name="Coursier")
    par = models.CharField("De", max_length=10, choices=PAR, default='support')
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='+', verbose_name="Écrit par")
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
                               verbose_name="Course concernée")
    texte = models.TextField("Message", max_length=2000)
    lu_le = models.DateTimeField("Lu le", null=True, blank=True)
    created_at = models.DateTimeField("Envoyé le", auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = "Message support ↔ coursier"
        verbose_name_plural = "Messages support ↔ coursiers"

    def __str__(self):
        return f"{self.get_par_display()} · {self.texte[:40]}"



class PromoCourse(models.Model):
    """Promotion sur les courses, PAYÉE PAR LANTANTE : le client paie moins, le coursier touche le prix entier
    (la remise lui est créditée sur son solde). Avec un code (le client le saisit) ou automatique (sans code)."""
    TYPES = [('montant', 'Montant fixe (FCFA)'), ('pct', 'Pourcentage')]
    nom = models.CharField("Nom", max_length=80, help_text="Ex. « Lancement Lantante Express ».")
    code = models.CharField("Code", max_length=30, blank=True,
                            help_text="Vide = promotion automatique (appliquée sans code aux clients concernés).")
    type = models.CharField("Type", max_length=8, choices=TYPES, default='montant')
    valeur = models.PositiveIntegerField("Valeur", help_text="FCFA ou % selon le type.")
    plafond = models.PositiveIntegerField("Remise maximum (FCFA)", null=True, blank=True)
    clients = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name='promos_courses',
                                     verbose_name="Clients concernés", help_text="Vide = tous les clients.")
    categories = models.ManyToManyField(Categorie, blank=True, verbose_name="Véhicules concernés",
                                        help_text="Vide = tous.")
    debut = models.DateTimeField("Début", null=True, blank=True)
    fin = models.DateTimeField("Fin", null=True, blank=True)
    max_utilisations = models.PositiveIntegerField("Utilisations max. (total)", null=True, blank=True)
    max_par_client = models.PositiveIntegerField("Utilisations max. par client", null=True, blank=True, default=1)
    actif = models.BooleanField("Active", default=True)
    created_at = models.DateTimeField("Créée le", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Promotion (courses)"
        verbose_name_plural = "Promotions (courses)"

    def __str__(self):
        return f"{self.nom} ({self.code or 'automatique'})"

    def save(self, *a, **kw):
        self.code = ''.join((self.code or '').split()).upper()
        super().save(*a, **kw)
