"""Codes promo : contrôle et calcul de la remise, côté serveur uniquement."""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

MIN_A_PAYER = 100
RESERVATION = timedelta(minutes=30)  # un paiement en attente « réserve » son code 30 min


def utilisations(code, user=None):
    from .models import Payment
    qs = Payment.objects.filter(code_promo=code).filter(
        Q(status='approved') | Q(status='pending', created_at__gte=timezone.now() - RESERVATION))
    return qs.filter(user=user) if user is not None else qs


def _cible_ok(c, fields):
    listes = {'produits': c.produits.all(), 'concours': c.concours.all(), 'formations': c.formations.all(),
              'evenements': c.evenements.all(), 'vendeurs': c.vendeurs.all()}
    if not any(l.exists() for l in listes.values()):
        return True  # valable partout
    kind = fields.get('kind')
    p = fields.get('product')
    if kind == 'product' and p is not None:
        return listes['produits'].filter(pk=p.pk).exists() or \
            (p.vendeur_id is not None and listes['vendeurs'].filter(pk=p.vendeur_id).exists())
    if kind == 'concours' and fields.get('contest') is not None:
        return listes['concours'].filter(pk=fields['contest'].pk).exists()
    if kind == 'formation' and fields.get('formation') is not None:
        return listes['formations'].filter(pk=fields['formation'].pk).exists()
    if kind in ('ticket', 'soutien') and fields.get('event') is not None:
        return listes['evenements'].filter(pk=fields['event'].pk).exists()
    return False


def remise(texte, user, fields, montant, verrou=False):
    """(remise en F, code). [montant] = total à payer avant remise (livraison comprise).
    La remise porte sur les articles, jamais sur la livraison. verrou=True dans une transaction de paiement."""
    from .models import CodePromo
    texte = ''.join(str(texte or '').split()).upper()
    if not texte:
        return 0, None
    if fields.get('kind') == 'depot':
        raise ValidationError("Pas de code promo pour une recharge.")
    qs = CodePromo.objects.select_for_update() if verrou else CodePromo.objects
    c = qs.filter(code=texte, actif=True).first()
    maintenant = timezone.now()
    if not c or (c.debut and c.debut > maintenant) or (c.fin and c.fin < maintenant):
        raise ValidationError("Code promo invalide ou expiré.")
    if not _cible_ok(c, fields):
        raise ValidationError("Ce code ne s'applique pas à cet achat.")
    articles = montant - int(fields.get('livraison') or 0)
    if articles < c.minimum_achat:
        raise ValidationError(f"Code valable dès {c.minimum_achat:,} F d'achat.".replace(',', ' '))
    if c.max_utilisations is not None and utilisations(c).count() >= c.max_utilisations:
        raise ValidationError("Ce code a déjà été utilisé le nombre de fois prévu.")
    if c.max_par_personne is not None and utilisations(c, user).count() >= c.max_par_personne:
        raise ValidationError("Vous avez déjà utilisé ce code.")
    r = articles * c.valeur // 100 if c.type == 'pct' else c.valeur
    r = min(r, articles, montant - MIN_A_PAYER)
    if r <= 0:
        raise ValidationError("Montant trop faible pour ce code.")
    return int(r), c
