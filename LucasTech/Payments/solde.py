"""Solde Lantante : SEULE porte d'entrée pour modifier un solde. Chaque opération verrouille le portefeuille
(select_for_update) dans une transaction, écrit un mouvement, et refuse tout solde négatif."""
import math
from decimal import Decimal

from django.db import IntegrityError, transaction

MIN_DEPOT = 100
MAX_DEPOT = 1_000_000
MAX_SOLDE = 4_000_000  # plafond par client
MIN_RETRAIT = 500


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


def debiter(user, montant, motif):
    """Débit hors paiement Mobile Money (ex. course Lantante Express). Lève SoldeInsuffisant."""
    if int(montant) <= 0:
        return None
    return _mouvement(user, -int(montant), 'paiement', motif=motif)


def debiter_jusqua(user, montant, motif):
    """Prend AU PLUS [montant] sur le solde (tout le solde s'il est plus petit). Renvoie ce qui a été pris."""
    from .models import Portefeuille
    montant = int(montant)
    if montant <= 0:
        return 0
    with transaction.atomic():
        Portefeuille.objects.get_or_create(user=user)
        pf = Portefeuille.objects.select_for_update().get(user=user)
        pris = min(pf.solde, montant)
        if pris > 0:
            _mouvement(user, -pris, 'paiement', motif=motif)
        return pris


def frais_retrait(montant):
    """Frais payés par le client, retenus sur le montant retiré (arrondis au franc supérieur)."""
    from courses.models import Parametres
    p = Parametres.get()
    frais = math.ceil(Decimal(int(montant)) * p.retrait_frais_pct / 100) if p.retrait_frais_pct else 0
    return max(int(frais), int(p.retrait_frais_min))


def demander_retrait(user, montant, numero, frais_vus=None):
    """Le montant quitte le solde tout de suite ; l'équipe envoie montant − frais puis marque « Payé »."""
    from .models import Portefeuille, RetraitClient
    try:
        montant = int(montant)
    except (TypeError, ValueError):
        raise ValueError("Montant invalide.")
    numero = ''.join(str(numero or '').split())
    if montant < MIN_RETRAIT:
        raise ValueError(f"Retrait minimum : {MIN_RETRAIT} CFA.")
    if not 8 <= len(numero.lstrip('+')) <= 15 or not numero.lstrip('+').isdigit():
        raise ValueError("Numéro Mobile Money invalide.")
    frais = frais_retrait(montant)
    if frais >= montant:
        raise ValueError("Montant trop faible par rapport aux frais.")
    # le client doit avoir vu les frais exacts avant de confirmer
    if frais and str(frais_vus) != str(frais):
        raise ValueError(f"Frais de retrait : {frais} CFA. Mettez à jour l'appli et confirmez à nouveau.")
    with transaction.atomic():
        Portefeuille.objects.get_or_create(user=user)
        Portefeuille.objects.select_for_update().get(user=user)
        if RetraitClient.objects.filter(user=user, statut='en_attente').exists():
            raise ValueError("Un retrait est déjà en cours.")
        r = RetraitClient.objects.create(user=user, montant=montant, frais=frais, numero=numero)
        _mouvement(user, -montant, 'retrait', motif=f"Retrait n° {r.pk} vers {numero}" + (f" (frais {frais} CFA)" if frais else ""))
    return r


def payer_retrait(retrait, par):
    from django.utils import timezone
    from .models import RetraitClient
    with transaction.atomic():
        r = RetraitClient.objects.select_for_update().get(pk=retrait.pk)
        if r.statut != 'en_attente':
            return False
        r.statut, r.traite_par, r.traite_le = 'paye', par, timezone.now()
        r.save(update_fields=['statut', 'traite_par', 'traite_le'])
    return True


def refuser_retrait(retrait, par, motif="Retrait refusé"):
    """Refus : l'argent revient sur le solde du client."""
    from django.utils import timezone
    from .models import RetraitClient
    with transaction.atomic():
        r = RetraitClient.objects.select_for_update().get(pk=retrait.pk)
        if r.statut != 'en_attente':
            return False
        r.statut, r.motif, r.traite_par, r.traite_le = 'refuse', motif[:255], par, timezone.now()
        r.save(update_fields=['statut', 'motif', 'traite_par', 'traite_le'])
        _mouvement(r.user, r.montant, 'remboursement', motif=f"Retrait n° {r.pk} refusé : montant rendu", par=par)
    return True


def rembourser(user, montant, motif, par=None):
    """Crédit d'un remboursement (course annulée, montant réservé libéré, geste commercial)."""
    if int(montant) <= 0:
        return None
    return _mouvement(user, int(montant), 'remboursement', motif=motif, par=par)
