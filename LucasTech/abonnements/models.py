"""Abonnements cumulables aux concours.

- Un utilisateur peut avoir plusieurs abonnements actifs en même temps.
- Les droits = l'union de tous ses abonnements (et extensions) actifs : voir abonnements.access.
- Prix et limite sont FIGÉS sur l'abonnement au moment de l'achat (changer la formule dans
  l'admin ne modifie pas les abonnements déjà vendus)."""
from django.conf import settings
from django.db import models
from django.utils import timezone

PERIOD_CHOICES = [('mois', 'Mensuel (30 jours)'), ('an', 'Annuel (365 jours)')]
PERIOD_DAYS = {'mois': 30, 'an': 365}

STATUS_CHOICES = [
    ('en_attente', 'En attente de paiement'),
    ('actif', 'Actif'),
    ('expire', 'Expiré'),
    ('annule', 'Annulé'),
    ('fusionne', 'Prolongation (fusionné)'),
]


class SubscriptionPlan(models.Model):
    code = models.SlugField("Code", max_length=30, unique=True, help_text="standard, premium, ultimate…")
    name = models.CharField("Nom", max_length=60)
    monthly_price = models.PositiveIntegerField("Prix mensuel (FCFA)")
    yearly_price = models.PositiveIntegerField("Prix annuel (FCFA)")
    contest_limit = models.PositiveSmallIntegerField("Nombre de concours", null=True, blank=True,
                                                     help_text="Laisser vide si illimité.")
    is_unlimited = models.BooleanField("Illimité", default=False,
                                       help_text="Accès à tous les concours ; un seul actif à la fois "
                                                 "(un nouvel achat prolonge la date de fin).")
    tagline = models.CharField("Accroche", max_length=160, blank=True)
    is_highlighted = models.BooleanField("Mise en avant", default=False)
    is_active = models.BooleanField("En vente", default=True)
    order = models.PositiveSmallIntegerField("Ordre", default=0)

    class Meta:
        ordering = ['order', 'monthly_price']
        verbose_name = "Formule d'abonnement"
        verbose_name_plural = "Formules d'abonnement"

    def __str__(self):
        return self.name

    def price_for(self, period):
        return self.yearly_price if period == 'an' else self.monthly_price

    @property
    def limit_label(self):
        if self.is_unlimited:
            return "Concours illimités"
        n = self.contest_limit or 0
        return f"{n} concours"

    @property
    def yearly_saving(self):
        return max(0, self.monthly_price * 12 - self.yearly_price)


class ExtensionOption(models.Model):
    slots = models.PositiveSmallIntegerField("Concours supplémentaires", unique=True)
    price = models.PositiveIntegerField("Prix pour 30 jours (FCFA)",
                                        help_text="Le prix réel est calculé au prorata des jours restants "
                                                  "de l'abonnement principal.")
    is_active = models.BooleanField("En vente", default=True)

    class Meta:
        ordering = ['slots']
        verbose_name = "Option d'extension"
        verbose_name_plural = "Options d'extension"

    def __str__(self):
        return f"+{self.slots} concours — {self.price} FCFA / 30 j"


class UserSubscriptionQuerySet(models.QuerySet):
    def active(self, now=None):
        """Actif = statut actif ET date de fin non dépassée (vérification à la volée)."""
        now = now or timezone.now()
        return self.filter(status='actif', start_at__lte=now, end_at__gt=now)


class UserSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contest_subscriptions',
                             verbose_name="Utilisateur")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions',
                             verbose_name="Formule")
    period = models.CharField("Durée", max_length=4, choices=PERIOD_CHOICES, default='mois')
    price_paid = models.PositiveIntegerField("Prix payé (FCFA)")
    contest_limit = models.PositiveSmallIntegerField("Limite de concours (figée)", null=True, blank=True)
    is_unlimited = models.BooleanField("Illimité (figé)", default=False)
    start_at = models.DateTimeField("Début", null=True, blank=True)
    end_at = models.DateTimeField("Fin", null=True, blank=True)
    status = models.CharField("Statut", max_length=12, choices=STATUS_CHOICES, default='en_attente', db_index=True)
    payment = models.ForeignKey('Payments.Payment', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='contest_subscriptions', verbose_name="Paiement")
    merged_into = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='merged', verbose_name="Prolonge l'abonnement")
    created_at = models.DateTimeField("Créé le", auto_now_add=True)
    activated_at = models.DateTimeField("Activé le", null=True, blank=True)

    objects = UserSubscriptionQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Abonnement utilisateur"
        verbose_name_plural = "Abonnements utilisateurs"

    def __str__(self):
        return f"{self.plan.name} #{self.pk} — {self.user}"

    @property
    def is_active(self):
        now = timezone.now()
        return (self.status == 'actif' and self.start_at is not None and self.end_at is not None
                and self.start_at <= now < self.end_at)

    def active_extensions(self):
        return [e for e in self.extensions.all() if e.status == 'actif']

    @property
    def extra_slots(self):
        return sum(e.slots for e in self.active_extensions())

    @property
    def total_limit(self):
        """None = illimité."""
        if self.is_unlimited:
            return None
        return (self.contest_limit or 0) + self.extra_slots

    @property
    def used_slots(self):
        return self.contests.count()

    @property
    def free_slots(self):
        if self.is_unlimited:
            return None
        return max(0, self.total_limit - self.used_slots)

    @property
    def days_left(self):
        if not self.end_at:
            return 0
        secs = (self.end_at - timezone.now()).total_seconds()
        return max(0, -int(-secs // 86400))  # arrondi au jour supérieur


class SubscriptionContest(models.Model):
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name='contests',
                                     verbose_name="Abonnement")
    contest = models.ForeignKey('concours.Contest', on_delete=models.PROTECT, related_name='subscription_links',
                                verbose_name="Concours")
    added_at = models.DateTimeField("Ajouté le", auto_now_add=True)

    class Meta:
        ordering = ['added_at']
        unique_together = [('subscription', 'contest')]
        verbose_name = "Concours sélectionné"
        verbose_name_plural = "Concours sélectionnés"

    def __str__(self):
        return f"{self.contest.acronym} (abonnement #{self.subscription_id})"


class SubscriptionExtension(models.Model):
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name='extensions',
                                     verbose_name="Abonnement principal")
    slots = models.PositiveSmallIntegerField("Concours supplémentaires")
    price_paid = models.PositiveIntegerField("Prix payé (FCFA)")
    status = models.CharField("Statut", max_length=12, choices=STATUS_CHOICES, default='en_attente', db_index=True)
    payment = models.ForeignKey('Payments.Payment', on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='subscription_extensions', verbose_name="Paiement")
    created_at = models.DateTimeField("Créée le", auto_now_add=True)
    activated_at = models.DateTimeField("Activée le", null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Extension d'abonnement"
        verbose_name_plural = "Extensions d'abonnement"

    def __str__(self):
        return f"+{self.slots} concours sur abonnement #{self.subscription_id}"


class SubscriptionAuditLog(models.Model):
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name='audit_logs',
                                     verbose_name="Abonnement")
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                              related_name='+', verbose_name="Administrateur")
    action = models.CharField("Action", max_length=60)
    details = models.TextField("Détails", blank=True)
    created_at = models.DateTimeField("Date", auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Journal d'audit (abonnements)"
        verbose_name_plural = "Journal d'audit (abonnements)"

    def __str__(self):
        return f"{self.created_at:%d/%m/%Y %H:%M} — {self.action}"
