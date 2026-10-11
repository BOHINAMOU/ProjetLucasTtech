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
                                       help_text="Ex : CDI, Stage")
    available = models.BooleanField(default=True, verbose_name="Disponible")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Téléphone / WhatsApp")
    cv = models.FileField(upload_to='cv/', storage=private_storage, blank=True,
                          verbose_name="CV (PDF)")

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
            'Contrats souhaités': self.contract_wanted,
            'Disponible': "oui" if self.available else "non",
            'Téléphone': self.phone,
            'CV': self.cv.name if self.cv else "",
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
    is_verified = models.BooleanField(default=False, verbose_name="Entreprise vérifiée",
                                      help_text="Seule une entreprise vérifiée par Lantante peut publier des offres "
                                                "et voir les CV autorisés.")
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
        ('pending', "En attente de validation"),
        ('published', "Publiée"),
        ('closed', "Clôturée"),
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
    deadline = models.DateField(null=True, blank=True, verbose_name="Date limite")
    status = models.CharField(max_length=10, choices=STATUS, default='pending', verbose_name="Statut")
    requires_cover_letter = models.BooleanField(default=False, verbose_name="Lettre de motivation demandée",
                                                help_text="Le candidat devra écrire une lettre de motivation pour postuler.")
    is_featured = models.BooleanField(default=False, verbose_name="À la une")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créée le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifiée le")

    class Meta:
        ordering = ['-is_featured', '-created_at']
        verbose_name = "Offre d'emploi"
        verbose_name_plural = "Offres d'emploi"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
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
        ('received', "Reçue"),
        ('shortlisted', "Présélectionné"),
        ('interview', "Entretien"),
        ('hired', "Embauché"),
        ('refused', "Refusé"),
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
    def employer(self):
        if self.offer_id and self.offer.employer_id:
            return self.offer.employer
        if self.request_id:
            return self.request.employer
        return None


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


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE,
                                     related_name='messages', verbose_name="Conversation")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name='sent_messages', verbose_name="Expéditeur")
    body = models.TextField(verbose_name="Message")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Envoyé le")
    read_by = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True,
                                     related_name='read_messages', verbose_name="Lu par")

    class Meta:
        ordering = ['created_at']
        verbose_name = "Message"
        verbose_name_plural = "Messages"

    def __str__(self):
        return f"{self.sender} : {self.body[:40]}"


# ─────────────────────────────
# 📅 RENDEZ-VOUS
# ─────────────────────────────
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
    image = models.ImageField(upload_to='emploi/feed/', blank=True, verbose_name="Image")
    is_hidden = models.BooleanField(default=False, verbose_name="Masquée (modération)")
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
    text = models.CharField(max_length=300, verbose_name="Message")
    url = models.CharField(max_length=300, blank=True, verbose_name="Lien")
    is_read = models.BooleanField(default=False, verbose_name="Lue")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return self.text
