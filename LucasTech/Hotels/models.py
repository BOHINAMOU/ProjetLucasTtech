"""Hôtels : fiche, photos, chambres (photos multiples), réservation par WhatsApp ou téléphone."""
from django.db import models
from django.utils.text import slugify

EQUIPEMENTS = [
    ('wifi', 'Wi-Fi'), ('clim', 'Climatisation'), ('parking', 'Parking'), ('piscine', 'Piscine'),
    ('restaurant', 'Restaurant'), ('petit_dejeuner', 'Petit-déjeuner'), ('tv', 'Télévision'),
    ('eau_chaude', 'Eau chaude'), ('groupe', 'Groupe électrogène'), ('securite', 'Sécurité 24 h/24'),
    ('salle_sport', 'Salle de sport'), ('navette', 'Navette aéroport'), ('salle_reunion', 'Salle de réunion'),
    ('bar', 'Bar'), ('plage', 'Accès plage'),
]
CODES = dict(EQUIPEMENTS)


class Hotel(models.Model):
    nom = models.CharField("Nom", max_length=140)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    ville = models.CharField("Ville", max_length=80, default='Lomé')
    quartier = models.CharField("Quartier / localité", max_length=120, blank=True)
    adresse = models.CharField("Adresse", max_length=200, blank=True)
    latitude = models.DecimalField("Latitude", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("Longitude", max_digits=9, decimal_places=6, null=True, blank=True)
    etoiles = models.PositiveSmallIntegerField("Étoiles", null=True, blank=True, help_text="Facultatif (1 à 5).")
    photo = models.ImageField("Photo principale", upload_to='hotels/', blank=True)
    legende_photo = models.CharField("Légende de la photo", max_length=60, blank=True,
                                     help_text="Ex. « Photo d'illustration » si ce n'est pas une photo de l'hôtel.")
    description = models.TextField("Présentation", blank=True)
    prix_min = models.PositiveIntegerField("À partir de (CFA / nuit)", null=True, blank=True,
                                           help_text="Facultatif. Vide = calculé depuis les chambres, sinon non affiché.")
    equipements = models.JSONField("Équipements", default=list, blank=True)
    telephone = models.CharField("Téléphone du propriétaire", max_length=30, blank=True)
    whatsapp = models.CharField("WhatsApp du propriétaire", max_length=30, blank=True,
                                help_text="Vide = notre WhatsApp principal (réglages du site).")
    site_web = models.URLField("Site web", blank=True)
    alias = models.CharField("Mots-clés", max_length=200, blank=True, help_text="Séparés par des virgules (recherche).")
    actif = models.BooleanField("Visible", default=True)
    ordre = models.PositiveSmallIntegerField("Ordre d'affichage", default=0)
    vues = models.PositiveIntegerField("Vues", default=0, editable=False)
    clics_reserver = models.PositiveIntegerField("Clics Réserver", default=0, editable=False)
    clics_appel = models.PositiveIntegerField("Clics Appeler", default=0, editable=False)
    created_at = models.DateTimeField("Ajouté le", auto_now_add=True)

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "Hôtel"
        verbose_name_plural = "Hôtels"

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nom)[:150] or 'hotel'
            s, i = base, 2
            while Hotel.objects.filter(slug=s).exclude(pk=self.pk).exists():
                s, i = f"{base}-{i}", i + 1
            self.slug = s
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('hotels:detail', args=[self.slug])

    @property
    def a_partir_de(self):
        if self.prix_min:
            return self.prix_min
        prix = [c.prix_nuit for c in self.chambres.all() if c.actif and c.prix_nuit]
        return min(prix) if prix else None


class PhotoHotel(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField("Photo", upload_to='hotels/photos/')
    legende = models.CharField("Légende", max_length=120, blank=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['ordre', 'pk']
        verbose_name = "Photo de l'hôtel"
        verbose_name_plural = "Photos de l'hôtel"


class Chambre(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='chambres')
    nom = models.CharField("Nom / type", max_length=120, help_text="Ex. Chambre double, Suite junior")
    prix_nuit = models.PositiveIntegerField("Prix par nuit (CFA)", null=True, blank=True)
    capacite = models.PositiveSmallIntegerField("Personnes", null=True, blank=True)
    description = models.TextField("Description", blank=True)
    equipements = models.JSONField("Équipements", default=list, blank=True)
    actif = models.BooleanField("Visible", default=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)
    vues = models.PositiveIntegerField("Vues", default=0, editable=False)

    class Meta:
        ordering = ['ordre', 'pk']
        verbose_name = "Chambre"
        verbose_name_plural = "Chambres"

    def __str__(self):
        return f"{self.nom} — {self.hotel.nom}"


class PhotoChambre(models.Model):
    chambre = models.ForeignKey(Chambre, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField("Photo", upload_to='hotels/chambres/')
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['ordre', 'pk']
        verbose_name = "Photo de la chambre"
        verbose_name_plural = "Photos de la chambre"
