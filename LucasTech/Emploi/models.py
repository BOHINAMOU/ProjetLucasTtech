from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

# Les CV sont stockés HORS du dossier « media » (qui est public) : ils ne
# sont accessibles que par une vue qui contrôle les droits.
private_storage = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)

DOMAIN_CHOICES = [
    ('informatique', "Informatique & numérique"),
    ('education', "Éducation & formation"),
    ('sante', "Santé"),
    ('commerce', "Commerce & vente"),
    ('gestion', "Gestion, comptabilité & administration"),
    ('btp', "BTP & construction"),
    ('industrie', "Industrie & maintenance"),
    ('agriculture', "Agriculture & agroalimentaire"),
    ('transport', "Transport & logistique"),
    ('hotellerie', "Hôtellerie, restauration & tourisme"),
    ('communication', "Communication & marketing"),
    ('droit', "Droit & juridique"),
    ('autre', "Autre"),
]

CONTRACT_CHOICES = [
    ('cdi', "CDI"),
    ('cdd', "CDD"),
    ('stage', "Stage"),
    ('alternance', "Alternance"),
    ('freelance', "Freelance / mission"),
    ('interim', "Intérim"),
    ('benevolat', "Bénévolat"),
]

INTERNSHIP_DURATION_CHOICES = [
    ("1 mois", "1 mois"), ("2 mois", "2 mois"), ("3 mois", "3 mois"), ("4 mois", "4 mois"),
    ("6 mois", "6 mois"), ("Plus de 6 mois", "Plus de 6 mois"),
]
OFFER_DURATION_CHOICES = [
    ("1 mois", "1 mois"), ("2 mois", "2 mois"), ("3 mois", "3 mois"), ("4 mois", "4 mois"), ("6 mois", "6 mois"),
    ("9 mois", "9 mois"), ("12 mois", "12 mois"), ("18 mois", "18 mois"), ("24 mois", "24 mois"),
    ("Plus de 24 mois", "Plus de 24 mois"),
]

LEVEL_CHOICES = [
    ('', "Non précisé"),
    ('bepc', "BEPC / niveau collège"),
    ('bac', "Baccalauréat"),
    ('bac2', "Bac +2 (BTS, DUT)"),
    ('bac3', "Bac +3 (Licence)"),
    ('bac5', "Bac +5 (Master, ingénieur)"),
    ('doctorat', "Doctorat"),
    ('autre', "Autre"),
]


class Skill(models.Model):
    name = models.CharField(max_length=80, unique=True, verbose_name="Compétence")

    class Meta:
        ordering = ['name']
        verbose_name = "Compétence"
        verbose_name_plural = "Compétences"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        super().save(*args, **kwargs)


# ─────────────────────────────
# 👤 CANDIDAT
# ─────────────────────────────
class CandidateProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='candidate_profile', verbose_name="Compte")
    headline = models.CharField(max_length=120, verbose_name="Titre du profil",
                                help_text="Ex : Développeur web, Enseignante de mathématiques…")
    domain = models.CharField(max_length=20, choices=DOMAIN_CHOICES, default='autre',
                              verbose_name="Domaine")
    skills = models.ManyToManyField(Skill, blank=True, related_name='candidates',
                                    verbose_name="Compétences")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    bio = models.TextField(blank=True, verbose_name="À propos")
    experience_years = models.PositiveSmallIntegerField(default=0, verbose_name="Années d'expérience")
    education_level = models.CharField(max_length=10, choices=LEVEL_CHOICES, blank=True,
                                       verbose_name="Niveau d'études")
    contract_wanted = models.CharField(max_length=120, blank=True, verbose_name="Types de contrat souhaités",
                                       help_text="Cochez un ou plusieurs types de contrat.")
    available = models.BooleanField(default=True, verbose_name="Disponible")
    seeking_internship = models.BooleanField(default=False, verbose_name="Je cherche un stage")
    internship_duration = models.CharField(max_length=60, blank=True, verbose_name="Durée de stage souhaitée",
                                           help_text="Ex : 3 mois, 6 mois")
    available_from = models.DateField(null=True, blank=True, verbose_name="Disponible à partir du")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Téléphone / WhatsApp")
    cv = models.FileField(upload_to='cv/', storage=private_storage, blank=True,
                          verbose_name="CV (PDF)")
    cover_letter = models.TextField(blank=True, verbose_name="Lettre de motivation",
                                    help_text="Rédigez-la une fois : elle est préremplie à chaque candidature (vous pouvez l'adapter à chaque offre).")

    # Ce que le candidat choisit de rendre public
    show_photo = models.BooleanField(default=True, verbose_name="Afficher ma photo")
    show_city = models.BooleanField(default=True, verbose_name="Afficher ma ville")
    show_bio = models.BooleanField(default=True, verbose_name="Afficher mon « À propos »")
    show_experience = models.BooleanField(default=True, verbose_name="Afficher mon expérience et mon niveau")
    # Contact et CV : privés par défaut — visibles seulement par Lantante et
    # (si le candidat l'accepte) par les recruteurs vérifiés.
    share_with_recruiters = models.BooleanField(
        default=False, verbose_name="Autoriser les recruteurs vérifiés à voir mon CV et mes contacts")

    is_published = models.BooleanField(default=True, verbose_name="Profil publié",
                                       help_text="Décochez pour masquer le profil du site.")
    admin_notes = models.TextField(blank=True, verbose_name="Notes internes Lantante")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")

    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Candidat"
        verbose_name_plural = "Candidats"

    def __str__(self):
        return f"{self.user.public_name} — {self.headline}"

    @property
    def name(self):
        return self.user.public_name

    def get_absolute_url(self):
        return reverse('emploi:candidate_detail', args=[self.pk])

    def live_profile_boost(self):
        """Boost de profil actif (jamais un facteur de sélection : seulement de visibilité)."""
        return self.boosts.filter(application__isnull=True, status='active', expires_at__gt=timezone.now()) \
            .order_by('-expires_at').first()

    @property
    def is_boosted(self):
        return self.live_profile_boost() is not None

    @property
    def contract_wanted_codes(self):
        valid = dict(CONTRACT_CHOICES)
        return [c for c in self.contract_wanted.split(',') if c in valid]

    @property
    def contract_wanted_display(self):
        labels = dict(CONTRACT_CHOICES)
        return ", ".join(labels[c] for c in self.contract_wanted_codes)

    def snapshot(self):
        """Copie des champs modifiables (pour l'historique interne)."""
        return {
            'Nom': self.user.get_full_name(),
            'Titre': self.headline,
            'Domaine': self.get_domain_display(),
            'Compétences': ", ".join(self.skills.values_list('name', flat=True)),
            'Ville': self.city,
            'À propos': self.bio,
            'Années d\'expérience': self.experience_years,
            'Niveau': self.get_education_level_display(),
            'Contrats souhaités': self.contract_wanted_display,
            'Disponible': "oui" if self.available else "non",
            'Téléphone': self.phone,
            'CV': self.cv.name if self.cv else "",
            'Lettre de motivation': self.cover_letter,
        }


class CandidateDocument(models.Model):
    """Diplôme, attestation ou autre pièce du candidat (privé, comme le CV)."""
    KIND = [('diplome', "Diplôme"), ('attestation', "Attestation / certificat"),
            ('identite', "Pièce d'identité"), ('autre', "Autre")]
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE,
                                  related_name='documents', verbose_name="Candidat")
    kind = models.CharField(max_length=12, choices=KIND, default='diplome', verbose_name="Type")
    title = models.CharField(max_length=120, verbose_name="Intitulé", help_text="Ex : Licence en Physique-Chimie")
    file = models.FileField(upload_to='candidate_docs/', storage=private_storage, verbose_name="Fichier (PDF ou photo)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ajouté le")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Document du candidat"
        verbose_name_plural = "Documents des candidats"

    def __str__(self):
        return f"{self.get_kind_display()} : {self.title}"


class ProfileRevision(models.Model):
    """Ancienne version d'un profil candidat, gardée en interne."""
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE,
                                  related_name='revisions', verbose_name="Candidat")
    data = models.JSONField(default=dict, verbose_name="Ancienne version")
    changed_fields = models.CharField(max_length=300, blank=True, verbose_name="Champs modifiés")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Remplacée le")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Ancienne version de profil"
        verbose_name_plural = "Historique des profils"

    def __str__(self):
        return f"{self.candidate.name} — {self.created_at:%d/%m/%Y %H:%M}"


# ─────────────────────────────
# 🏢 ENTREPRISE / RECRUTEUR
# ─────────────────────────────
class EmployerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='employer_profile', verbose_name="Compte")
    partner = models.OneToOneField('core.Partner', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='employer', verbose_name="Fiche partenaire liée",
                                   help_text="Si l'entreprise est aussi partenaire, ses offres apparaîtront sur sa fiche partenaire.")
    company_name = models.CharField(max_length=150, verbose_name="Nom de l'entreprise")
    logo = models.ImageField(upload_to='emploi/logos/', blank=True, verbose_name="Logo")
    sector = models.CharField(max_length=20, choices=DOMAIN_CHOICES, default='autre', verbose_name="Secteur")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    description = models.TextField(blank=True, verbose_name="Présentation")
    products = models.TextField(blank=True, verbose_name="Produits / services",
                                help_text="Un par ligne.")
    website = models.URLField(blank=True, verbose_name="Site web")
    whatsapp = models.CharField(max_length=30, blank=True, verbose_name="WhatsApp",
                                help_text="Numéro complet, ex : 22890000000")
    contact_email = models.EmailField(blank=True, verbose_name="Email de contact")
    employees_count = models.PositiveIntegerField(null=True, blank=True, verbose_name="Nombre d'employés")
    document = models.FileField(
        upload_to='employer_docs/', storage=private_storage, blank=True,
        verbose_name="Document de présentation (Word, Excel ou PDF)",
        help_text="Explique votre entreprise et ce que vous recherchez. Visible uniquement par Lantante.")
    STATUS = [
        ('pending', "En cours d'analyse"),
        ('approved', "Acceptée"),
        ('rejected', "Refusée"),
    ]
    status = models.CharField(max_length=10, choices=STATUS, default='pending', verbose_name="Décision de Lantante",
                              help_text="Une entreprise acceptée peut déposer autant de demandes et d'offres qu'elle veut.")
    decision_message = models.TextField(
        blank=True, verbose_name="Message à l'entreprise",
        help_text="Conditions, contrat proposé ou motif du refus. Envoyé à l'entreprise quand vous changez la décision.")
    decided_at = models.DateTimeField(null=True, blank=True, verbose_name="Décision prise le")
    is_verified = models.BooleanField(default=False, verbose_name="Badge bleu (entreprise de confiance)",
                                      help_text="Badge bleu affiché sur ses pages. Ses offres sont publiées directement, "
                                                "sans validation.")
    publishing_free = models.BooleanField(
        default=False, verbose_name="Publications incluses (partenaire officiel / contrat)",
        help_text="Cochez pour un partenaire dont le contrat inclut les publications : il ne paie rien. "
                  "Avec le badge bleu, ses publications sont mises en ligne directement.")
    admin_notes = models.TextField(blank=True, verbose_name="Notes internes Lantante")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créée le")

    class Meta:
        ordering = ['company_name']
        verbose_name = "Entreprise"
        verbose_name_plural = "Entreprises"

    def __str__(self):
        return self.company_name

    def get_absolute_url(self):
        return reverse('emploi:company_detail', args=[self.pk])

    @property
    def is_approved(self):
        return self.status == 'approved'

    @property
    def logo_url(self):
        if self.logo:
            return self.logo.url
        if self.partner_id and self.partner.logo:
            return self.partner.logo.url
        return ''

    @property
    def product_list(self):
        return [l.strip() for l in self.products.splitlines() if l.strip()]


# ─────────────────────────────
# 💼 OFFRES ET DEMANDES
# ─────────────────────────────
class JobOffer(models.Model):
    STATUS = [
        ('awaiting_payment', "En attente de paiement"),
        ('pending', "En attente de validation"),
        ('published', "Publiée"),
        ('filled', "Pourvue (poste pourvu)"),
        ('closed', "Terminée (date de fin dépassée)"),
        ('rejected', "Refusée"),
    ]
    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, null=True, blank=True,
                                 related_name='offers', verbose_name="Entreprise",
                                 help_text="Laisser vide pour une offre publiée directement par Lantante.")
    title = models.CharField(max_length=160, verbose_name="Intitulé du poste")
    slug = models.SlugField(max_length=190, unique=True, blank=True)
    domain = models.CharField(max_length=20, choices=DOMAIN_CHOICES, default='autre', verbose_name="Domaine")
    contract = models.CharField(max_length=12, choices=CONTRACT_CHOICES, default='cdi', verbose_name="Contrat")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    description = models.TextField(verbose_name="Description du poste")
    requirements = models.TextField(blank=True, verbose_name="Profil recherché")
    skills = models.ManyToManyField(Skill, blank=True, related_name='offers', verbose_name="Compétences")
    salary = models.CharField(max_length=100, blank=True, verbose_name="Rémunération")
    duration = models.CharField(max_length=60, blank=True, verbose_name="Durée (stage, CDD…)",
                                help_text="Ex : 3 mois")
    deadline = models.DateField(null=True, blank=True, verbose_name="Date de fin",
                                help_text="À cette date, l'offre disparaît automatiquement du site et de l'espace de l'entreprise.")
    status = models.CharField(max_length=20, choices=STATUS, default='pending', verbose_name="Statut")
    cover_image = models.ImageField(upload_to='emploi/offers/', blank=True, verbose_name="Photo de couverture",
                                    help_text="Illustre l'offre dans les listes. Sans photo, un visuel coloré est affiché.")
    requires_cover_letter = models.BooleanField(default=False, verbose_name="Lettre de motivation demandée",
                                                help_text="Le candidat devra écrire une lettre de motivation pour postuler.")
    is_featured = models.BooleanField(default=False, verbose_name="À la une")
    featured_until = models.DateTimeField(null=True, blank=True, verbose_name="À la une jusqu'au",
                                          help_text="Rempli par une mise en avant payée ; vide = sans limite.")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créée le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifiée le")

    class Meta:
        ordering = ['-is_featured', '-created_at']
        verbose_name = "Offre d'emploi"
        verbose_name_plural = "Offres d'emploi"

    def __str__(self):
        return self.title

    DOMAIN_ICONS = {
        'informatique': 'fa-laptop-code', 'education': 'fa-graduation-cap', 'sante': 'fa-heart-pulse',
        'commerce': 'fa-store', 'gestion': 'fa-chart-line', 'btp': 'fa-helmet-safety',
        'industrie': 'fa-gears', 'agriculture': 'fa-seedling', 'transport': 'fa-truck',
        'hotellerie': 'fa-utensils', 'communication': 'fa-bullhorn', 'droit': 'fa-scale-balanced',
    }
    DOMAIN_GRADIENTS = {
        'informatique': '#0d3b7a,#1d6fe0', 'education': '#0f7a45,#34d399', 'sante': '#be185d,#f472b6',
        'commerce': '#b8420a,#f59e0b', 'gestion': '#163a63,#0f7a45', 'btp': '#92400e,#f59e0b',
        'industrie': '#334155,#64748b', 'agriculture': '#166534,#84cc16', 'transport': '#1e3a8a,#38bdf8',
        'hotellerie': '#9a3412,#fb923c', 'communication': '#6d28d9,#c084fc', 'droit': '#1f2937,#6b7280',
    }

    @property
    def domain_icon(self):
        return self.DOMAIN_ICONS.get(self.domain, 'fa-briefcase')

    @property
    def cover_gradient(self):
        return self.DOMAIN_GRADIENTS.get(self.domain, '#0d3b7a,#0f7a45')

    def save(self, *args, **kwargs):
        # Photo trop lourde : on la réduit à l'envoi (1600 px max) pour garder un site rapide.
        if self.cover_image and not self.cover_image._committed:
            try:
                import io
                from django.core.files.base import ContentFile
                from PIL import Image
                img = Image.open(self.cover_image)
                img = img.convert('RGB')
                img.thumbnail((1600, 1000))
                buf = io.BytesIO()
                img.save(buf, 'JPEG', quality=85, optimize=True)
                name = self.cover_image.name.rsplit('.', 1)[0] + '.jpg'
                self.cover_image.save(name, ContentFile(buf.getvalue()), save=False)
            except Exception:
                pass
        if not self.slug:
            base = slugify(self.title)[:170] or 'offre'
            slug, n = base, 2
            while JobOffer.objects.filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('emploi:offer_detail', args=[self.slug])

    @classmethod
    def expire_featured(cls):
        """Une mise en avant payée s'arrête à sa date de fin."""
        return cls.objects.filter(is_featured=True, featured_until__lt=timezone.now()).update(is_featured=False)

    @classmethod
    def close_expired(cls):
        """Les offres dont la date de fin est dépassée disparaissent (statut « Terminée »)."""
        return cls.objects.filter(status='published', deadline__lt=timezone.localdate()).update(status='closed')

    @property
    def company_name(self):
        return self.employer.company_name if self.employer_id else "Lantante Technologie"

    @property
    def is_open(self):
        if self.status != 'published':
            return False
        return not self.deadline or self.deadline >= timezone.localdate()


class StaffingRequest(models.Model):
    """Demande de recrutement confiée à Lantante par une entreprise."""
    STATUS = [
        ('new', "Nouvelle"),
        ('in_progress', "En cours de traitement"),
        ('proposed', "Candidats proposés"),
        ('filled', "Pourvue"),
        ('cancelled', "Annulée"),
    ]
    URGENCY = [('normal', "Normale"), ('urgent', "Urgente")]

    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE,
                                 related_name='requests', verbose_name="Entreprise")
    title = models.CharField(max_length=160, verbose_name="Poste recherché")
    domain = models.CharField(max_length=20, choices=DOMAIN_CHOICES, default='autre', verbose_name="Domaine")
    positions = models.PositiveSmallIntegerField(default=1, verbose_name="Nombre de postes")
    contract = models.CharField(max_length=12, choices=CONTRACT_CHOICES, default='cdi', verbose_name="Contrat")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    description = models.TextField(verbose_name="Détail du besoin")
    skills = models.ManyToManyField(Skill, blank=True, related_name='requests', verbose_name="Compétences")
    urgency = models.CharField(max_length=10, choices=URGENCY, default='normal', verbose_name="Urgence")
    status = models.CharField(max_length=12, choices=STATUS, default='new', verbose_name="Statut")
    admin_notes = models.TextField(blank=True, verbose_name="Notes internes Lantante")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Reçue le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifiée le")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Demande de recrutement"
        verbose_name_plural = "Demandes de recrutement"

    def __str__(self):
        return f"{self.title} — {self.employer.company_name}"


# ─────────────────────────────
# 🔗 CANDIDATURES / SUIVI
# ─────────────────────────────
class Application(models.Model):
    """Lien entre un candidat et une offre (ou une demande) + suivi du recrutement."""
    STATUS = [
        ('received', "En attente"),
        ('shortlisted', "Présélectionné"),
        ('interview', "Entretien"),
        ('hired', "Accepté"),
        ('refused', "Rejeté"),
        ('treated', "Traité"),
    ]
    ORIGIN = [('candidate', "Le candidat a postulé"), ('lantante', "Proposé par Lantante")]

    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE,
                                  related_name='applications', verbose_name="Candidat")
    offer = models.ForeignKey(JobOffer, on_delete=models.CASCADE, null=True, blank=True,
                              related_name='applications', verbose_name="Offre")
    request = models.ForeignKey(StaffingRequest, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='applications', verbose_name="Demande de recrutement")
    origin = models.CharField(max_length=10, choices=ORIGIN, default='candidate', verbose_name="Origine")
    message = models.TextField(blank=True, verbose_name="Message du candidat")
    cover_letter = models.TextField(blank=True, verbose_name="Lettre de motivation")
    internship_duration = models.CharField(max_length=60, blank=True, verbose_name="Durée de stage souhaitée")
    available_from = models.DateField(null=True, blank=True, verbose_name="Disponible à partir du")
    status_message = models.TextField(
        blank=True, verbose_name="Message au candidat (motif du refus, précisions)",
        help_text="Envoyé au candidat avec le changement de statut. Pour un refus, indiquez le motif.")
    CONSENT = [('accepted', "Accord du candidat"), ('pending', "En attente de l'accord du candidat"),
               ('declined', "Refusé par le candidat")]
    consent = models.CharField(max_length=10, choices=CONSENT, default='accepted', verbose_name="Accord pour la transmission",
                               help_text="Une opportunité proposée par Lantante n'est transmise à l'entreprise qu'avec l'accord du candidat.")
    spontaneous = models.ForeignKey('SpontaneousRequest', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='applications', verbose_name="Demande spontanée d'origine")
    shared_with_employer = models.BooleanField(
        default=False, verbose_name="Dossier transmis à l'entreprise",
        help_text="Tant que Lantante ne transmet pas le dossier, l'entreprise ne voit ni le CV ni les coordonnées.")
    shared_at = models.DateTimeField(null=True, blank=True, verbose_name="Transmis le")
    status = models.CharField(max_length=12, choices=STATUS, default='received', verbose_name="Statut")
    admin_notes = models.TextField(blank=True, verbose_name="Notes internes Lantante")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Mise à jour")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Candidature / mise en relation"
        verbose_name_plural = "Candidatures et mises en relation"

    def __str__(self):
        target = self.offer or self.request
        return f"{self.candidate.name} → {target}"

    @property
    def missing_items(self):
        """Éléments manquants du dossier (indicateur « Dossier incomplet », sans statut à part)."""
        missing = []
        if not self.candidate.cv:
            missing.append("CV")
        if not (self.candidate.phone or self.candidate.user.phone):
            missing.append("numéro de téléphone")
        if self.offer_id and self.offer.requires_cover_letter and not self.cover_letter.strip():
            missing.append("lettre de motivation")
        if self.offer_id and self.offer.contract == 'stage' and not self.internship_duration:
            missing.append("durée de stage souhaitée")
        return missing

    @property
    def is_incomplete(self):
        return bool(self.missing_items)

    @property
    def step_index(self):
        """Position dans le parcours affiché au candidat : attente, présélection, entretien, accepté."""
        return {'received': 0, 'shortlisted': 1, 'interview': 2, 'hired': 3, 'treated': 3}.get(self.status, -1)

    @property
    def employer(self):
        if self.offer_id and self.offer.employer_id:
            return self.offer.employer
        if self.request_id:
            return self.request.employer
        return None


class AvailabilitySlot(models.Model):
    """Créneau proposé par un candidat présélectionné pour son entretien."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='slots',
                                    verbose_name="Candidature")
    start = models.DateTimeField(verbose_name="Disponible le")
    note = models.CharField(max_length=200, blank=True, verbose_name="Précision")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start']
        verbose_name = "Disponibilité pour l'entretien"
        verbose_name_plural = "Disponibilités pour l'entretien"

    def __str__(self):
        return f"{self.start:%d/%m/%Y %H:%M}"


class Placement(models.Model):
    """Contrat / placement : suivi d'une embauche obtenue grâce à Lantante."""
    STATUS = [('in_progress', "En cours"), ('signed', "Contrat signé"),
              ('started', "Candidat en poste"), ('ended', "Terminé"), ('cancelled', "Annulé")]

    application = models.OneToOneField(Application, on_delete=models.CASCADE,
                                       related_name='placement', verbose_name="Candidature")
    contract = models.CharField(max_length=12, choices=CONTRACT_CHOICES, default='cdi', verbose_name="Type de contrat")
    start_date = models.DateField(null=True, blank=True, verbose_name="Date de début")
    end_date = models.DateField(null=True, blank=True, verbose_name="Date de fin")
    salary = models.CharField(max_length=100, blank=True, verbose_name="Rémunération")
    fee = models.CharField(max_length=100, blank=True, verbose_name="Frais / commission Lantante")
    status = models.CharField(max_length=12, choices=STATUS, default='in_progress', verbose_name="Statut")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Contrat / placement"
        verbose_name_plural = "Contrats et placements"

    def __str__(self):
        return str(self.application)


# ─────────────────────────────
# 💬 MESSAGERIE
# ─────────────────────────────
class Conversation(models.Model):
    subject = models.CharField(max_length=160, blank=True, verbose_name="Sujet")
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='conversations',
                                          verbose_name="Participants")
    KIND = [('direct', "Conversation directe"), ('support', "Service client Lantante")]
    STATUS = [('new', "Reçue"), ('assigned', "Prise en charge"), ('closed', "Clôturée")]
    kind = models.CharField(max_length=8, choices=KIND, default='direct', verbose_name="Type")
    status = models.CharField(max_length=8, choices=STATUS, default='new', verbose_name="Statut")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_conversations', verbose_name="Collaborateur responsable",
        limit_choices_to=models.Q(is_staff=True) | models.Q(is_superuser=True))
    auto_reply_sent = models.BooleanField(default=False, verbose_name="Accusé de réception envoyé")
    intro_sent = models.BooleanField(default=False, verbose_name="Présentation du collaborateur envoyée")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créée le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Dernier message")

    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Conversation"
        verbose_name_plural = "Messagerie (supervision)"

    def __str__(self):
        return self.subject or f"Conversation #{self.pk}"

    def other_participants(self, user):
        return self.participants.exclude(pk=user.pk)

    def requesters(self):
        """Les personnes extérieures à l'équipe qui ont écrit à Lantante."""
        return self.participants.filter(is_staff=False, is_superuser=False)

    def title_for(self, user):
        """Titre affiché selon qui regarde la conversation."""
        if self.kind == 'support':
            if user.is_staff or user.is_superuser:
                return ", ".join(u.public_name for u in self.requesters()) or "Demande"
            return "Lantante Technologie"
        return ", ".join(u.public_name for u in self.participants.all() if u.pk != user.pk)


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE,
                                     related_name='messages', verbose_name="Conversation")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                               related_name='sent_messages', verbose_name="Expéditeur")
    is_automatic = models.BooleanField(default=False, verbose_name="Message automatique")
    is_intro = models.BooleanField(default=False, verbose_name="Présentation automatique du collaborateur")
    body = models.TextField(verbose_name="Message")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Envoyé le")
    read_by = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True,
                                     related_name='read_messages', verbose_name="Lu par")

    class Meta:
        ordering = ['created_at']
        verbose_name = "Message"
        verbose_name_plural = "Messages"

    def __str__(self):
        return f"{self.author_name} : {self.body[:40]}"

    @property
    def is_from_staff(self):
        return bool(self.sender_id and (self.sender.is_staff or self.sender.is_superuser))

    @property
    def author_name(self):
        if self.is_automatic or not self.sender_id:
            return "Lantante Technologie"
        if self.is_from_staff:
            return self.sender.get_full_name().strip() or "Membre de l'équipe"
        return self.sender.public_name

    @property
    def author_role(self):
        if self.is_automatic or not self.sender_id:
            return "Message automatique"
        if self.is_from_staff:
            title = getattr(getattr(self.sender, 'staff_profile', None), 'job_title', '')
            return "Équipe Lantante Technologie" + (f" · {title}" if title else "")
        return ""


# ─────────────────────────────
# 📅 RENDEZ-VOUS
# ─────────────────────────────
class ModerationWarning(models.Model):
    """Avertissement donné par Lantante à un utilisateur. À 3 avertissements actifs, le compte est suspendu."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='moderation_warnings', verbose_name="Utilisateur")
    reason = models.TextField(verbose_name="Motif", help_text="Expliqué à la personne dans l'avertissement.")
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='+', verbose_name="Donné par")
    is_active = models.BooleanField(default=True, verbose_name="Compte dans les 3 avertissements",
                                    help_text="Décoché automatiquement quand un bannissement est levé : le compteur repart de zéro.")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Avertissement"
        verbose_name_plural = "Avertissements"

    def __str__(self):
        return f"{self.user} — {self.reason[:40]}"


class AccountBan(models.Model):
    """Bannissement (compte bloqué). Jamais supprimé : on garde l'historique, même après réactivation."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='ban', verbose_name="Utilisateur")
    reason = models.TextField(verbose_name="Motif")
    automatic = models.BooleanField(default=False, verbose_name="Automatique (3 avertissements)")
    banned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='+', verbose_name="Décidé par")
    banned_at = models.DateTimeField(default=timezone.now, verbose_name="Banni le")
    lifted_at = models.DateTimeField(null=True, blank=True, verbose_name="Levé le")

    class Meta:
        ordering = ['-banned_at']
        verbose_name = "Bannissement"
        verbose_name_plural = "Bannissements"

    def __str__(self):
        return f"{self.user} — {'levé' if self.lifted_at else 'banni'}"

    @property
    def is_current(self):
        return self.lifted_at is None


class ServicePlan(models.Model):
    """Un service payant proposé aux entreprises (tarif modifiable dans l'administration)."""
    KIND = [
        ('news', "Actualité"),
        ('news_boost', "Actualité mise en avant"),
        ('job', "Offre d'emploi"),
        ('ad', "Publicité avec visuels"),
        ('recruit', "Accompagnement au recrutement"),
        ('job_boost', "Mise en avant d'une offre"),
        ('cand_boost', "Boost de profil (candidat) — retiré"),
        ('cand_app', "Boost d'une candidature (candidat)"),
    ]
    EMPLOYER_KINDS = ('news', 'news_boost', 'job', 'job_boost', 'ad', 'recruit')
    MEMBER_KINDS = ('news', 'news_boost', 'ad')  # un particulier publie une actualité ou une annonce, jamais d'offre d'emploi
    CANDIDATE_KINDS = ('cand_boost', 'cand_app')
    code = models.SlugField(max_length=30, unique=True, verbose_name="Code")
    kind = models.CharField(max_length=12, choices=KIND, verbose_name="Type de service")
    name = models.CharField(max_length=100, verbose_name="Nom affiché")
    description = models.TextField(blank=True, verbose_name="Ce qui est inclus")
    price = models.PositiveIntegerField(default=0, verbose_name="Prix (FCFA)",
                                        help_text="0 = gratuit. Pour un service sur devis, laissez 0 et cochez « Sur devis ».")
    price_from = models.BooleanField(default=False, verbose_name="« À partir de »")
    quote_only = models.BooleanField(default=False, verbose_name="Sur devis",
                                     help_text="Lantante contacte l'entreprise et fixe le montant avant le paiement.")
    duration_days = models.PositiveSmallIntegerField(default=0, verbose_name="Durée de visibilité (jours)",
                                                     help_text="0 = sans limite.")
    is_active = models.BooleanField(default=True, verbose_name="Proposé",
                                    help_text="Décochez pour retirer ce service des formules.")
    order = models.PositiveSmallIntegerField(default=0, verbose_name="Ordre")

    class Meta:
        ordering = ['order', 'price']
        verbose_name = "Tarif"
        verbose_name_plural = "Tarifs des services"

    def __str__(self):
        return f"{self.name} — {self.price_label}"

    @property
    def advantages(self):
        """Avantages affichés un par un (la description les sépare par « · » ou par un retour à la ligne)."""
        import re
        return [p.strip(' .') for p in re.split(r'\s*(?:·|\n)\s*', self.description) if p.strip(' .')]

    @property
    def price_label(self):
        if self.quote_only:
            return "Sur devis"
        if self.price == 0:
            return "Gratuit"
        amount = f"{self.price:,}".replace(",", " ")
        return f"{'À partir de ' if self.price_from else ''}{amount} FCFA"


class PublicationOrder(models.Model):
    """Commande de publication d'une entreprise : choix du service, paiement, validation, mise en ligne."""
    STATUS = [
        ('quote', "En attente de devis"),
        ('awaiting_payment', "À payer"),
        ('payment_declared', "Paiement à vérifier"),
        ('in_review', "En cours de validation"),
        ('changes_requested', "À corriger"),
        ('published', "Publiée"),
        ('refused', "Refusée"),
        ('refunded', "Remboursée"),
        ('cancelled', "Annulée"),
    ]
    METHODS = [('flooz', "Flooz"), ('tmoney', "T-Money"), ('other', "Autre moyen")]
    employer = models.ForeignKey(EmployerProfile, on_delete=models.CASCADE, null=True, blank=True,
                                 related_name='orders', verbose_name="Entreprise")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                             related_name='publication_orders', verbose_name="Compte",
                             help_text="Entreprise ou particulier qui publie.")
    boosted_offer = models.ForeignKey('JobOffer', on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='boost_orders', verbose_name="Offre mise en avant")
    plan = models.ForeignKey(ServicePlan, on_delete=models.PROTECT, related_name='orders', verbose_name="Service")
    status = models.CharField(max_length=20, choices=STATUS, default='awaiting_payment', verbose_name="Statut")
    amount = models.PositiveIntegerField(default=0, verbose_name="Montant (FCFA)")

    # contenu à publier (actualité, mise en avant, publicité)
    title = models.CharField(max_length=160, blank=True, verbose_name="Titre")
    text = models.TextField(blank=True, verbose_name="Texte")
    image = models.ImageField(upload_to='emploi/orders/', blank=True, verbose_name="Image")
    link_url = models.URLField(blank=True, verbose_name="Lien (publicité)")
    post_kind = models.CharField(max_length=8, default='news', verbose_name="Type d'actualité",
                                 choices=[('news', "Actualité"), ('product', "Nouveau produit / service")])
    job_offer = models.OneToOneField('JobOffer', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='order', verbose_name="Offre liée")
    staffing_request = models.OneToOneField('StaffingRequest', on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='order', verbose_name="Demande liée")
    feed_post = models.OneToOneField('FeedPost', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='order', verbose_name="Publication en ligne")

    # paiement (manuel pour l'instant ; prêt pour un paiement en ligne)
    provider = models.CharField(max_length=10, default='manual', verbose_name="Mode d'encaissement")
    payment_method = models.CharField(max_length=10, choices=METHODS, blank=True, verbose_name="Moyen de paiement")
    payer_phone = models.CharField(max_length=30, blank=True, verbose_name="Numéro ayant payé")
    payment_reference = models.CharField(max_length=80, blank=True, verbose_name="Référence de la transaction")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Paiement confirmé le")
    receipt_number = models.CharField(max_length=20, blank=True, verbose_name="N° de reçu")

    # décision de Lantante
    review_message = models.TextField(blank=True, verbose_name="Message à l'entreprise",
                                      help_text="Correction demandée, motif de refus, devis… envoyé à l'entreprise.")
    internal_note = models.TextField(blank=True, verbose_name="Note interne")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créée le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifiée le")
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="Publiée le")
    visible_until = models.DateTimeField(null=True, blank=True, verbose_name="Visible jusqu'au")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Commande de publication"
        verbose_name_plural = "Commandes et paiements"

    def __str__(self):
        return f"#{self.pk} {self.plan.name} — {self.owner_name}"

    @property
    def owner_name(self):
        if self.employer_id:
            return self.employer.company_name
        return self.user.public_name if self.user_id else "—"

    @property
    def reference(self):
        return f"LT-{self.created_at:%y}{self.pk:05d}" if self.pk else ""

    @property
    def amount_label(self):
        if self.amount == 0:
            return "Gratuit" if self.status != 'quote' else "Devis en attente"
        return f"{self.amount:,}".replace(",", " ") + " FCFA"

    @property
    def can_pay(self):
        return self.status == 'awaiting_payment' and self.amount > 0

    @property
    def can_edit(self):
        return self.status in ('awaiting_payment', 'changes_requested', 'quote')

    @property
    def step_index(self):
        """Étape affichée : 0 soumise, 1 paiement, 2 validation, 3 publiée."""
        return {'quote': 0, 'awaiting_payment': 1, 'payment_declared': 1, 'in_review': 2, 'changes_requested': 2,
                'published': 3}.get(self.status, -1)


class SpontaneousRequest(models.Model):
    """Demande spontanée : le candidat se fait connaître même sans offre ; Lantante garde la demande dans son vivier."""
    TYPES = [
        ('job', "Emploi"),
        ('intern_academic', "Stage académique"),
        ('intern_pro', "Stage professionnel"),
        ('alternance', "Alternance"),
        ('other', "Autre opportunité"),
    ]
    STATUS = [
        ('pending', "En attente"),
        ('in_progress', "En cours de traitement"),
        ('matched', "Profil correspondant à une opportunité"),
        ('transmitted', "Transmise à une entreprise"),
        ('interview', "Entretien proposé"),
        ('closed', "Clôturée"),
        ('rejected', "Rejetée"),
    ]
    OPEN_STATUSES = ('pending', 'in_progress', 'matched', 'transmitted', 'interview')
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='spontaneous_requests',
                                  verbose_name="Candidat")
    request_type = models.CharField(max_length=16, choices=TYPES, default='job', verbose_name="Type de demande")
    domain = models.CharField(max_length=20, choices=DOMAIN_CHOICES, default='autre', verbose_name="Domaine recherché")
    skills = models.ManyToManyField(Skill, blank=True, related_name='spontaneous_requests', verbose_name="Compétences")
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville souhaitée")
    available_from = models.DateField(null=True, blank=True, verbose_name="Disponible à partir du")
    duration = models.CharField(max_length=60, blank=True, verbose_name="Durée souhaitée (stage, alternance)")
    message = models.TextField(blank=True, verbose_name="Ce que vous recherchez")
    status = models.CharField(max_length=12, choices=STATUS, default='pending', verbose_name="Statut")
    status_message = models.TextField(blank=True, verbose_name="Message au candidat",
                                      help_text="Envoyé au candidat avec le changement de statut.")
    withdrawn = models.BooleanField(default=False, verbose_name="Retirée par le candidat")
    admin_notes = models.TextField(blank=True, verbose_name="Notes internes Lantante")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Déposée le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Mise à jour")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Demande spontanée"
        verbose_name_plural = "Demandes spontanées"

    def __str__(self):
        return f"{self.candidate.name} — {self.get_request_type_display()}"

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def can_edit(self):
        return self.status in ('pending', 'in_progress', 'matched')


class BoostOrder(models.Model):
    """Boost de visibilité d'un candidat (profil ou candidature précise). Il ne garantit ni présélection ni entretien."""
    STATUS = [
        ('awaiting_payment', "À payer"),
        ('payment_declared', "Paiement à vérifier"),
        ('active', "Actif"),
        ('refunded', "Remboursé"),
        ('cancelled', "Annulé"),
    ]
    METHODS = [('flooz', "Flooz"), ('tmoney', "T-Money"), ('other', "Autre moyen")]
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='boosts',
                                  verbose_name="Candidat")
    plan = models.ForeignKey(ServicePlan, on_delete=models.PROTECT, related_name='boosts', verbose_name="Formule")
    application = models.ForeignKey(Application, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='boosts', verbose_name="Candidature boostée",
                                    help_text="Vide = boost du profil entier.")
    status = models.CharField(max_length=20, choices=STATUS, default='awaiting_payment', verbose_name="Statut")
    amount = models.PositiveIntegerField(default=0, verbose_name="Montant (FCFA)")
    provider = models.CharField(max_length=10, default='manual', verbose_name="Mode d'encaissement")
    payment_method = models.CharField(max_length=10, choices=METHODS, blank=True, verbose_name="Moyen de paiement")
    payer_phone = models.CharField(max_length=30, blank=True, verbose_name="Numéro ayant payé")
    payment_reference = models.CharField(max_length=80, blank=True, verbose_name="Référence de la transaction")
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name="Paiement confirmé le")
    receipt_number = models.CharField(max_length=20, blank=True, verbose_name="N° de reçu")
    starts_at = models.DateTimeField(null=True, blank=True, verbose_name="Actif depuis le")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Expire le")
    internal_note = models.TextField(blank=True, verbose_name="Note interne")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Demandé le")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Boost de candidat"
        verbose_name_plural = "Boosts des candidats"

    def __str__(self):
        return f"#{self.pk} {self.plan.name} — {self.candidate.name}"

    @property
    def reference(self):
        return f"BO-{self.created_at:%y}{self.pk:05d}" if self.pk else ""

    @property
    def amount_label(self):
        return f"{self.amount:,}".replace(",", " ") + " FCFA"

    @property
    def is_live(self):
        return self.status == 'active' and bool(self.expires_at) and self.expires_at > timezone.now()

    @property
    def is_expired(self):
        return self.status == 'active' and bool(self.expires_at) and self.expires_at <= timezone.now()

    @property
    def days_left(self):
        return max((self.expires_at - timezone.now()).days, 0) if self.is_live else 0

    @property
    def can_pay(self):
        return self.status == 'awaiting_payment'

    @property
    def state_label(self):
        if self.is_expired:
            return "Expiré"
        return self.get_status_display()


class DeviceToken(models.Model):
    """Téléphone d'un utilisateur (application mobile) pour lui envoyer des notifications push."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_tokens',
                             verbose_name="Utilisateur")
    token = models.CharField(max_length=255, unique=True, verbose_name="Jeton Expo")
    platform = models.CharField(max_length=10, blank=True, verbose_name="Plateforme")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Téléphone enregistré"
        verbose_name_plural = "Téléphones enregistrés"

    def __str__(self):
        return f"{self.user} ({self.platform})"


class StaffProfile(models.Model):
    """Fonction d'un membre de l'équipe Lantante (affichée quand il se présente aux candidats)."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='staff_profile', verbose_name="Collaborateur",
                                limit_choices_to=models.Q(is_staff=True) | models.Q(is_superuser=True))
    job_title = models.CharField(max_length=100, verbose_name="Fonction",
                                 help_text="Ex : Responsable recrutement, Chargé de clientèle")

    class Meta:
        verbose_name = "Fonction d'un collaborateur"
        verbose_name_plural = "Fonctions des collaborateurs"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} — {self.job_title}"


class Appointment(models.Model):
    STATUS = [('proposed', "Proposé"), ('confirmed', "Confirmé"),
              ('declined', "Refusé"), ('done', "Effectué"), ('cancelled', "Annulé")]

    application = models.ForeignKey(Application, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='appointments', verbose_name="Candidature liée")
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE,
                                  related_name='appointments', verbose_name="Candidat")
    employer = models.ForeignKey(EmployerProfile, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='appointments', verbose_name="Entreprise")
    title = models.CharField(max_length=160, default="Entretien", verbose_name="Objet")
    scheduled_at = models.DateTimeField(verbose_name="Date et heure")
    place = models.CharField(max_length=200, blank=True, verbose_name="Lieu / lien visio")
    status = models.CharField(max_length=10, choices=STATUS, default='proposed', verbose_name="Statut")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        ordering = ['scheduled_at']
        verbose_name = "Rendez-vous"
        verbose_name_plural = "Rendez-vous"

    def __str__(self):
        return f"{self.title} — {self.candidate.name} ({self.scheduled_at:%d/%m/%Y %H:%M})"


# ─────────────────────────────
# 📰 FIL D'ACTUALITÉS
# ─────────────────────────────
class FeedPost(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='feed_posts', verbose_name="Auteur")
    text = models.TextField(verbose_name="Texte")
    KIND = [('news', "Actualité"), ('product', "Nouveau produit / service")]
    kind = models.CharField(max_length=8, choices=KIND, default='news', verbose_name="Type")
    image = models.ImageField(upload_to='emploi/feed/', blank=True, verbose_name="Image")
    is_hidden = models.BooleanField(default=False, verbose_name="Masquée (modération)")
    is_featured = models.BooleanField(default=False, verbose_name="Mise en avant (en haut du fil)")
    featured_until = models.DateTimeField(null=True, blank=True, verbose_name="Mise en avant jusqu'au")
    is_sponsored = models.BooleanField(default=False, verbose_name="Publicité (affiche « Sponsorisé »)")
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True,
                                   related_name='liked_posts', verbose_name="J'aime")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Publiée le")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Publication du fil"
        verbose_name_plural = "Fil d'actualités"

    def __str__(self):
        return f"{self.author.public_name} : {self.text[:50]}"

    @property
    def author_verified(self):
        employer = getattr(self.author, 'employer_profile', None)
        return bool(employer and employer.is_verified)

    @property
    def author_employer(self):
        return getattr(self.author, 'employer_profile', None)

    @property
    def author_label(self):
        employer = getattr(self.author, 'employer_profile', None)
        if employer:
            return employer.company_name
        return self.author.public_name


class FeedComment(models.Model):
    post = models.ForeignKey(FeedPost, on_delete=models.CASCADE, related_name='comments', verbose_name="Publication")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Auteur")
    text = models.TextField(max_length=1000, verbose_name="Commentaire")
    is_hidden = models.BooleanField(default=False, verbose_name="Masqué")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date")

    class Meta:
        ordering = ['created_at']
        verbose_name = "Commentaire"
        verbose_name_plural = "Commentaires"

    def __str__(self):
        return self.text[:50]


# ─────────────────────────────
# 🔔 NOTIFICATIONS
# ─────────────────────────────
class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='emploi_notifications', verbose_name="Destinataire")
    text = models.TextField(verbose_name="Message")
    url = models.CharField(max_length=300, blank=True, verbose_name="Lien")
    is_read = models.BooleanField(default=False, verbose_name="Lue")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return self.text
