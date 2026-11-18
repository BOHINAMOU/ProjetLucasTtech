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
    kind = fields.get('kind')
    if not c.abonnement and not any(l.exists() for l in listes.values()):
        return True  # valable partout
    if kind == 'acces':
        return c.abonnement
    p = fields.get('product')
    if kind == 'product' and p is not None:
        return listes['produits'].filter(pk=p.pk).exists() or \
            (p.vendeur_id is not None and listes['vendeurs'].filter(pk=p.vendeur_id).exists())
    if kind == 'shop':
        its = fields.get('items') or []
        pids = [i['product'] for i in its if i.get('product')]
        fids = [i['formation'] for i in its if i.get('formation')]
        v = fields.get('vendeur')
        return listes['produits'].filter(pk__in=pids).exists() or listes['formations'].filter(pk__in=fids).exists() or \
            (v is not None and listes['vendeurs'].filter(pk=v.pk).exists())
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
        raise ValidationError("Code non valable ici")
    qs = CodePromo.objects.select_for_update() if verrou else CodePromo.objects
    c = qs.filter(code=texte, actif=True).first()
    maintenant = timezone.now()
    if not c or (c.debut and c.debut > maintenant):
        raise ValidationError("Code invalide")
    if c.fin and c.fin < maintenant:
        raise ValidationError("Code expiré")
    if not _cible_ok(c, fields):
        raise ValidationError("Code non valable ici")
    articles = montant - int(fields.get('livraison') or 0)
    if articles < c.minimum_achat:
        raise ValidationError(f"Code dès {c.minimum_achat:,} CFA d'achat".replace(',', ' '))
    if c.max_utilisations is not None and utilisations(c).count() >= c.max_utilisations:
        raise ValidationError("Code épuisé")
    if c.max_par_personne is not None and utilisations(c, user).count() >= c.max_par_personne:
        raise ValidationError("Code déjà utilisé")
    r = articles * c.valeur // 100 if c.type == 'pct' else c.valeur
    r = min(r, articles, montant - MIN_A_PAYER)
    if r <= 0:
        raise ValidationError("Montant trop faible")
    return int(r), c
