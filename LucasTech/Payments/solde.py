"""Solde Lantante : SEULE porte d'entrée pour modifier un solde. Chaque opération verrouille le portefeuille
(select_for_update) dans une transaction, écrit un mouvement, et refuse tout solde négatif."""
from django.db import IntegrityError, transaction

MIN_DEPOT = 100
MAX_DEPOT = 1_000_000
MAX_SOLDE = 4_000_000  # plafond par client


class SoldeInsuffisant(Exception):
    pass


def portefeuille(user):
    from .models import Portefeuille
    return Portefeuille.objects.get_or_create(user=user)[0]


def _mouvement(user, montant, type, payment=None, motif='', par=None):
    from .models import MouvementSolde, Portefeuille
    with transaction.atomic():
        Portefeuille.objects.get_or_create(user=user)
        pf = Portefeuille.objects.select_for_update().get(user=user)
        if payment is not None and MouvementSolde.objects.filter(payment=payment, type=type).exists():
            return None  # déjà fait (idempotence)
        nouveau = pf.solde + montant
        if nouveau < 0:
            raise SoldeInsuffisant()
        if montant > 0 and nouveau > MAX_SOLDE:
            raise ValueError("Plafond du solde atteint.")
        pf.solde = nouveau
        pf.save(update_fields=['solde', 'updated_at'])
        try:
            with transaction.atomic():
                return MouvementSolde.objects.create(portefeuille=pf, type=type, montant=montant, solde_apres=nouveau,
                                                     payment=payment, motif=motif[:255], par=par)
        except IntegrityError:
            # course entre deux webhooks : l'autre a déjà crédité, on annule notre mise à jour
            raise _Doublon()


class _Doublon(Exception):
    pass


def crediter_depot(payment):
    """Appelé à la livraison d'un paiement « depot » réussi : crédite UNE fois."""
    try:
        with transaction.atomic():
            return _mouvement(payment.user, int(payment.amount), 'depot', payment=payment, motif="Recharge Mobile Money")
    except _Doublon:
        return None


def payer_avec_solde(user, montant, payment):
    """Débite le solde pour [payment] (lève SoldeInsuffisant)."""
    return _mouvement(user, -int(montant), 'paiement', payment=payment, motif=payment.description)


def ajuster(user, montant, motif, par):
    if not motif.strip():
        raise ValueError("Le motif est obligatoire.")
    return _mouvement(user, int(montant), 'ajustement', motif=motif, par=par)
