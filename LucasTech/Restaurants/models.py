"""Restaurants : fiche, photos (carrousel), plats, options (accompagnements, boissons…) et commande par WhatsApp."""
import re

from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Restaurant(models.Model):
    nom = models.CharField("Nom", max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    logo = models.ImageField("Logo", upload_to='restaurants/logos/', blank=True)
    couverture = models.ImageField("Photo principale", upload_to='restaurants/couvertures/', blank=True)
    description = models.TextField("Description", blank=True)
    quartier = models.CharField("Quartier", max_length=120, blank=True)
    ville = models.CharField("Ville", max_length=80, default='Lomé')
    adresse = models.CharField("Adresse / repère", max_length=200, blank=True)
    latitude = models.DecimalField("Latitude", max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField("Longitude", max_digits=9, decimal_places=6, null=True, blank=True)
    horaires = models.TextField("Horaires", blank=True, help_text="Ex. Lun–Sam : 10 h – 22 h")
    telephone = models.CharField("Téléphone", max_length=30, blank=True)
    whatsapp = models.CharField("WhatsApp des commandes", max_length=30, blank=True,
                                help_text="Vide : les commandes arrivent sur le WhatsApp de Lantante.")
    livraison = models.CharField("Livraison", max_length=160, blank=True, help_text="Ex. Livraison à Lomé, ou « Sur place et à emporter »")
    visible = models.BooleanField("Visible", default=True, db_index=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)
    vues = models.PositiveIntegerField("Vues", default=0, editable=False)
    clics_commander = models.PositiveIntegerField("Clics « Commander »", default=0, editable=False)
    created_at = models.DateTimeField("Ajouté le", auto_now_add=True)

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "Restaurant"
        verbose_name_plural = "Restaurants"

    def __str__(self):
        return self.nom

    def save(self, *a, **k):
        if not self.slug:
            base = slugify(self.nom)[:120] or 'restaurant'
            s, i = base, 2
            while Restaurant.objects.filter(slug=s).exclude(pk=self.pk).exists():
                s, i = f"{base}-{i}", i + 1
            self.slug = s
        super().save(*a, **k)

    def get_absolute_url(self):
        return reverse('restaurants:detail', args=[self.slug])

    @property
    def lieu(self):
        return ', '.join(x for x in (self.quartier, self.ville) if x)


class PhotoRestaurant(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField("Photo (menu, plat phare…)", upload_to='restaurants/photos/')
    legende = models.CharField("Légende", max_length=100, blank=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['ordre', 'pk']
        verbose_name = "Photo du carrousel"
        verbose_name_plural = "Photos du carrousel"


class CategoriePlat(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='categories')
    nom = models.CharField("Catégorie", max_length=80)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "Catégorie de plats"
        verbose_name_plural = "Catégories de plats"

    def __str__(self):
        return self.nom


class Plat(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='plats')
    categorie = models.ForeignKey(CategoriePlat, on_delete=models.SET_NULL, null=True, blank=True, related_name='plats',
                                  verbose_name="Catégorie")
    nom = models.CharField("Nom du plat", max_length=120)
    description = models.TextField("Description", blank=True)
    prix = models.PositiveIntegerField("Prix (CFA)")
    image = models.ImageField("Photo", upload_to='restaurants/plats/', blank=True)
    disponible = models.BooleanField("Disponible", default=True, db_index=True)
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "Plat"
        verbose_name_plural = "Plats"

    def __str__(self):
        return f"{self.nom} ({self.restaurant})"

    def groupes(self):
        """Options du plat, puis celles valables pour tout le restaurant."""
        return list(self.groupes_options.all()) + list(self.restaurant.groupes_options.filter(plat__isnull=True))


class PhotoPlat(models.Model):
    plat = models.ForeignKey(Plat, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField("Photo", upload_to='restaurants/plats/')
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['ordre', 'pk']
        verbose_name = "Autre photo"
        verbose_name_plural = "Autres photos"


LIGNE = re.compile(r'^\s*(.+?)\s*(?:[|=:;]|\s-\s|\s)\s*(\d[\d\s.]*)\s*(?:f?\s*cfa|f)?\s*$', re.I)


def lire_options(texte):
    """« Alloco | 500 » ou « Coca 33 cl = 500 » ou « Sans piment » (gratuit) → [{'nom', 'prix'}]."""
    out = []
    for ligne in (texte or '').splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        m = LIGNE.match(ligne)
        if m:
            out.append({'nom': m.group(1).strip(' -'), 'prix': int(re.sub(r'\D', '', m.group(2)) or 0)})
        else:
            out.append({'nom': ligne, 'prix': 0})
    return out


class GroupeOptions(models.Model):
    """Ex. « Accompagnements » : Alloco 500, Frites 700… Sur un plat, ou pour tout le restaurant (plat vide)."""
    CHOIX = [('unique', 'Un seul choix'), ('multiple', 'Plusieurs choix')]
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='groupes_options')
    plat = models.ForeignKey(Plat, on_delete=models.CASCADE, null=True, blank=True, related_name='groupes_options',
                             help_text="Vide : ces options sont proposées pour tous les plats du restaurant.")
    nom = models.CharField("Nom du groupe", max_length=80, help_text="Ex. Accompagnements, Boissons, Fruits")
    choix = models.CharField("Choix", max_length=8, choices=CHOIX, default='multiple')
    obligatoire = models.BooleanField("Obligatoire", default=False)
    avec_quantite = models.BooleanField("Quantité par option", default=False)
    options_texte = models.TextField("Options et prix", help_text="Une option par ligne : « Alloco | 500 ». Prix 0 possible.")
    ordre = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['ordre', 'pk']
        verbose_name = "Groupe d'options"
        verbose_name_plural = "Groupes d'options"

    def __str__(self):
        return self.nom

    @property
    def options(self):
        return lire_options(self.options_texte)

    def as_dict(self):
        return {'id': self.pk, 'nom': self.nom, 'choix': self.choix, 'obligatoire': self.obligatoire,
                'avec_quantite': self.avec_quantite,
                'options': [{'id': i, **o} for i, o in enumerate(self.options)]}
