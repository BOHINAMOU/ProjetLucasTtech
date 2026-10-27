"""Portfolio personnel de BOHINAMOU Matieyendou Lucas, affiché sur /bohinamou/.
Tout le contenu se modifie dans l'administration (menu « Portfolio »)."""
from django.db import models
from django.utils.text import slugify


def _unique_slug(model, base, instance):
    slug = base = slugify(base) or 'element'
    n = 1
    while model.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


# ─────────────────────────────
# 👤 PROFIL (une seule fiche)
# ─────────────────────────────
class Profile(models.Model):
    full_name = models.CharField(max_length=150, default="BOHINAMOU Matieyendou Lucas", verbose_name="Nom complet")
    title = models.CharField(max_length=150, default="Ingénieur des travaux informatiques", verbose_name="Titre professionnel")
    tagline = models.CharField(
        max_length=250, blank=True, default="Développement logiciel · Solutions numériques · Communication digitale",
        verbose_name="Domaines (sous le titre)", help_text="Séparez les domaines par « · ».")
    photo = models.ImageField(upload_to='portfolio/', blank=True, null=True, verbose_name="Photo",
                              help_text="Une photo de bonne qualité, de préférence en portrait.")
    intro = models.TextField(blank=True, verbose_name="Phrase d'accueil",
                             help_text="Une ou deux phrases affichées sous le titre, en haut de la page.")
    bio = models.TextField(
        blank=True, verbose_name="Qui est Bohinamou ? (texte)",
        help_text="Votre présentation. Séparez les paragraphes par une ligne vide. Le texte apparaît petit à petit quand on clique.")
    cv = models.FileField(upload_to='portfolio/cv/', blank=True, null=True, verbose_name="CV (PDF)")
    availability = models.CharField(max_length=200, blank=True, verbose_name="Disponibilité",
                                    help_text="Ex : Disponible pour des missions et collaborations.")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville / pays", help_text="Ex : Lomé, Togo")
    email = models.EmailField(blank=True, verbose_name="E-mail professionnel (affiché)")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Téléphone (affiché)")
    whatsapp = models.CharField(max_length=20, blank=True, verbose_name="WhatsApp",
                                help_text="Numéro complet avec l'indicatif, sans + ni espaces. Ex : 22890000000")

    website = models.URLField(blank=True, verbose_name="Site web")
    linkedin = models.URLField(blank=True, verbose_name="LinkedIn")
    github = models.URLField(blank=True, verbose_name="GitHub")
    facebook = models.URLField(blank=True, verbose_name="Facebook")
    instagram = models.URLField(blank=True, verbose_name="Instagram")
    tiktok = models.URLField(blank=True, verbose_name="TikTok")
    youtube = models.URLField(blank=True, verbose_name="YouTube")
    x_twitter = models.URLField(blank=True, verbose_name="X (Twitter)")

    class Meta:
        verbose_name = "Profil"
        verbose_name_plural = "Profil"

    def __str__(self):
        return self.full_name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def bio_paragraphs(self):
        return [p.strip() for p in self.bio.replace('\r', '').split('\n\n') if p.strip()]

    @property
    def tagline_list(self):
        return [t.strip() for t in self.tagline.replace('|', '·').split('·') if t.strip()]

    @property
    def initials(self):
        parts = [p for p in self.full_name.split() if p]
        return ''.join(p[0] for p in parts[:2]).upper() or 'B'

    @property
    def socials(self):
        """Réseaux renseignés : [(nom, icône Font Awesome, lien)]."""
        items = [
            ('LinkedIn', 'fa-brands fa-linkedin-in', self.linkedin),
            ('GitHub', 'fa-brands fa-github', self.github),
            ('Facebook', 'fa-brands fa-facebook-f', self.facebook),
            ('Instagram', 'fa-brands fa-instagram', self.instagram),
            ('TikTok', 'fa-brands fa-tiktok', self.tiktok),
            ('YouTube', 'fa-brands fa-youtube', self.youtube),
            ('X', 'fa-brands fa-x-twitter', self.x_twitter),
            ('WhatsApp', 'fa-brands fa-whatsapp', f"https://wa.me/{self.whatsapp}" if self.whatsapp else ''),
            ('Site web', 'fa-solid fa-globe', self.website),
        ]
        return [(n, i, u) for n, i, u in items if u]


# ─────────────────────────────
# 🛠 COMPÉTENCES (technologies)
# ─────────────────────────────
class Skill(models.Model):
    CATEGORIES = [
        ('lang', 'Langages'),
        ('frame', 'Frameworks et bibliothèques'),
        ('data', 'Bases de données'),
        ('tools', 'Outils et systèmes'),
        ('soft', 'Gestion et communication'),
    ]
    LEVELS = [
        ('', "Non indiqué"),
        ('notions', "Notions"),
        ('inter', "Intermédiaire"),
        ('avance', "Avancé"),
        ('expert', "Expert"),
    ]
    name = models.CharField(max_length=80, verbose_name="Nom")
    category = models.CharField(max_length=10, choices=CATEGORIES, default='lang', verbose_name="Catégorie")
    icon_class = models.CharField(
        max_length=120, blank=True, verbose_name="Logo (classe Devicon)",
        help_text="Ex : devicon-python-plain colored — liste sur devicon.dev. Laissez vide si vous envoyez une image.")
    logo = models.ImageField(upload_to='portfolio/skills/', blank=True, null=True, verbose_name="Logo (image)")
    level = models.CharField(max_length=10, choices=LEVELS, blank=True, default='', verbose_name="Niveau")
    description = models.TextField(blank=True, verbose_name="C'est quoi ?",
                                   help_text="Explication simple de cette technologie, affichée quand on clique dessus.")
    usage = models.TextField(blank=True, verbose_name="Comment je l'utilise",
                             help_text="Facultatif : vos usages, projets ou expériences avec cette technologie.")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    is_active = models.BooleanField(default=True, verbose_name="Affichée")

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Compétence"
        verbose_name_plural = "Compétences"

    def __str__(self):
        return self.name


# ─────────────────────────────
# 🚀 PROJETS
# ─────────────────────────────
class Project(models.Model):
    title = models.CharField(max_length=200, verbose_name="Titre")
    slug = models.SlugField(max_length=220, unique=True, blank=True, verbose_name="Adresse (automatique)")
    client = models.CharField(max_length=150, blank=True, verbose_name="Client / organisation")
    summary = models.CharField(max_length=300, verbose_name="Résumé court", help_text="Une ou deux phrases, affichées sur la carte.")
    description = models.TextField(blank=True, verbose_name="Description détaillée",
                                   help_text="Le problème résolu, les fonctionnalités, les résultats. Séparez les paragraphes par une ligne vide.")
    role = models.CharField(max_length=200, blank=True, verbose_name="Mon rôle")
    image = models.ImageField(upload_to='portfolio/projects/', blank=True, null=True, verbose_name="Image principale")
    skills = models.ManyToManyField(Skill, blank=True, related_name='projects', verbose_name="Technologies utilisées")
    link = models.URLField(blank=True, verbose_name="Lien du projet", help_text="Laissez vide si le site n'est pas public.")
    year = models.PositiveIntegerField(blank=True, null=True, verbose_name="Année")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    is_published = models.BooleanField(default=True, verbose_name="Publié")

    class Meta:
        ordering = ['order', '-year', 'title']
        verbose_name = "Projet"
        verbose_name_plural = "Projets"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(Project, self.title, self)
        super().save(*args, **kwargs)

    @property
    def description_paragraphs(self):
        return [p.strip() for p in self.description.replace('\r', '').split('\n\n') if p.strip()]


class ProjectImage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='images', verbose_name="Projet")
    image = models.ImageField(upload_to='portfolio/projects/', verbose_name="Image")
    caption = models.CharField(max_length=200, blank=True, verbose_name="Légende")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Image du projet"
        verbose_name_plural = "Images du projet"

    def __str__(self):
        return self.caption or f"Image {self.pk}"


# ─────────────────────────────
# 🧰 CE QUE JE SAIS FAIRE
# ─────────────────────────────
class Service(models.Model):
    title = models.CharField(max_length=150, verbose_name="Titre")
    description = models.TextField(verbose_name="Description")
    icon = models.CharField(max_length=60, default='fa-solid fa-laptop-code', verbose_name="Icône (Font Awesome)",
                            help_text="Ex : fa-solid fa-laptop-code — liste sur fontawesome.com/icons")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    is_active = models.BooleanField(default=True, verbose_name="Affiché")

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Service (ce que je sais faire)"
        verbose_name_plural = "Services (ce que je sais faire)"

    def __str__(self):
        return self.title


# ─────────────────────────────
# 🎓 CERTIFICATS ET ATTESTATIONS
# ─────────────────────────────
class Certificate(models.Model):
    KINDS = [
        ('certification', 'Certification'),
        ('attestation', 'Attestation'),
        ('formation', 'Formation suivie'),
        ('diplome', 'Diplôme'),
        ('autre', 'Autre'),
    ]
    title = models.CharField(max_length=200, verbose_name="Intitulé")
    kind = models.CharField(max_length=15, choices=KINDS, default='attestation', verbose_name="Type")
    organization = models.CharField(max_length=200, blank=True, verbose_name="Organisme")
    date = models.DateField(blank=True, null=True, verbose_name="Date")
    image = models.ImageField(upload_to='portfolio/certificates/', blank=True, null=True, verbose_name="Image du document")
    file = models.FileField(upload_to='portfolio/certificates/', blank=True, null=True, verbose_name="Fichier PDF")
    verify_url = models.URLField(blank=True, verbose_name="Lien de vérification")
    description = models.TextField(blank=True, verbose_name="Description")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    is_active = models.BooleanField(default=True, verbose_name="Affiché")

    class Meta:
        ordering = ['order', '-date']
        verbose_name = "Certificat / attestation"
        verbose_name_plural = "Certificats et attestations"

    def __str__(self):
        return self.title


# ─────────────────────────────
# 🤝 COLLABORATEURS
# ─────────────────────────────
class Collaborator(models.Model):
    full_name = models.CharField(max_length=150, verbose_name="Nom complet")
    role = models.CharField(max_length=150, blank=True, verbose_name="Fonction")
    photo = models.ImageField(upload_to='portfolio/collaborators/', blank=True, null=True, verbose_name="Photo")
    bio = models.TextField(blank=True, verbose_name="Présentation", help_text="Séparez les paragraphes par une ligne vide.")
    expertise = models.CharField(max_length=300, blank=True, verbose_name="Domaines d'expertise", help_text="Séparés par des virgules.")
    common_projects = models.TextField(blank=True, verbose_name="Projets réalisés ensemble", help_text="Un projet par ligne.")
    website = models.URLField(blank=True, verbose_name="Site web")
    linkedin = models.URLField(blank=True, verbose_name="LinkedIn")
    facebook = models.URLField(blank=True, verbose_name="Facebook")
    whatsapp = models.CharField(max_length=20, blank=True, verbose_name="WhatsApp", help_text="Numéro complet sans + ni espaces.")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    is_active = models.BooleanField(default=True, verbose_name="Affiché")

    class Meta:
        ordering = ['order', 'full_name']
        verbose_name = "Collaborateur"
        verbose_name_plural = "Collaborateurs"

    def __str__(self):
        return self.full_name

    @property
    def initials(self):
        return ''.join(p[0] for p in self.full_name.split()[:2]).upper() or '?'

    @property
    def bio_paragraphs(self):
        return [p.strip() for p in self.bio.replace('\r', '').split('\n\n') if p.strip()]

    @property
    def expertise_list(self):
        return [x.strip() for x in self.expertise.split(',') if x.strip()]

    @property
    def common_projects_list(self):
        return [x.strip() for x in self.common_projects.splitlines() if x.strip()]

    @property
    def links(self):
        items = [
            ('LinkedIn', 'fa-brands fa-linkedin-in', self.linkedin),
            ('Facebook', 'fa-brands fa-facebook-f', self.facebook),
            ('WhatsApp', 'fa-brands fa-whatsapp', f"https://wa.me/{self.whatsapp}" if self.whatsapp else ''),
            ('Site web', 'fa-solid fa-globe', self.website),
        ]
        return [(n, i, u) for n, i, u in items if u]


# ─────────────────────────────
# 🕰 PARCOURS (formation, expériences)
# ─────────────────────────────
class Experience(models.Model):
    KINDS = [
        ('formation', 'Formation'),
        ('experience', 'Expérience professionnelle'),
        ('stage', 'Stage'),
        ('parcours', 'Autre étape de mon parcours'),
    ]
    kind = models.CharField(max_length=12, choices=KINDS, default='parcours', verbose_name="Type")
    title = models.CharField(max_length=200, verbose_name="Intitulé")
    organization = models.CharField(max_length=200, blank=True, verbose_name="Organisme / entreprise")
    period = models.CharField(max_length=80, blank=True, verbose_name="Période", help_text="Ex : 2024 – 2026")
    description = models.TextField(blank=True, verbose_name="Description")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre", help_text="Du plus récent (petit nombre) au plus ancien.")
    is_active = models.BooleanField(default=True, verbose_name="Affiché")

    class Meta:
        ordering = ['order', '-id']
        verbose_name = "Étape du parcours"
        verbose_name_plural = "Parcours (formations et expériences)"

    def __str__(self):
        return self.title


# ─────────────────────────────
# 🌍 ENGAGEMENT ASSOCIATIF
# ─────────────────────────────
class Engagement(models.Model):
    title = models.CharField(max_length=200, verbose_name="Intitulé")
    organization = models.CharField(max_length=200, blank=True, verbose_name="Association / organisation")
    role = models.CharField(max_length=150, blank=True, verbose_name="Ma responsabilité")
    period = models.CharField(max_length=80, blank=True, verbose_name="Période")
    description = models.TextField(blank=True, verbose_name="Description")
    link = models.URLField(blank=True, verbose_name="Lien")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    is_active = models.BooleanField(default=True, verbose_name="Affiché")

    class Meta:
        ordering = ['order', '-id']
        verbose_name = "Engagement associatif"
        verbose_name_plural = "Engagements associatifs"

    def __str__(self):
        return self.title


# ─────────────────────────────
# 📊 CHIFFRES
# ─────────────────────────────
class Stat(models.Model):
    value = models.CharField(max_length=30, verbose_name="Chiffre", help_text="Ex : 12+")
    label = models.CharField(max_length=80, verbose_name="Légende", help_text="Ex : Projets réalisés")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    is_active = models.BooleanField(default=True, verbose_name="Affiché")

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Chiffre clé"
        verbose_name_plural = "Chiffres clés"

    def __str__(self):
        return f"{self.value} {self.label}"


# ─────────────────────────────
# ✉️ MESSAGES REÇUS
# ─────────────────────────────
class ContactMessage(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nom")
    contact = models.CharField(max_length=150, verbose_name="E-mail ou téléphone")
    message = models.TextField(verbose_name="Message")
    is_read = models.BooleanField(default=False, verbose_name="Lu")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Reçu le")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Message reçu"
        verbose_name_plural = "Messages reçus"

    def __str__(self):
        return f"{self.name} — {self.message[:40]}"
