"""Cycle d'une candidature : paiement confirmé → vérification → validée (fiche publiée), à corriger ou rejetée."""
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Candidature, HistoriqueCandidature, Repetiteur

DELAI_PURGE = timedelta(days=90)


def _site():
    return (getattr(settings, 'SITE_URL', '') or 'https://lantantetechnologie.com').rstrip('/')


def _trace(c, action, auteur='', motif=''):
    HistoriqueCandidature.objects.create(candidature=c, action=action, auteur=str(auteur or ''), motif=motif)


def _ecrire(c, sujet, texte):
    """E-mail au candidat (adresse du dossier, sinon celle du compte). Une erreur d'envoi ne bloque rien."""
    dest = c.email or getattr(c.user, 'email', '')
    if not dest:
        return
    lien = _site() + '/repetiteurs/ma-candidature/'
    try:
        send_mail(sujet, f"Bonjour {c.prenom},\n\n{texte}\n\nVotre dossier : {lien}\n\nL'équipe Lantante",
                  settings.DEFAULT_FROM_EMAIL, [dest], fail_silently=True)
    except Exception:
        pass


def paiement_confirme(payment):
    """Appelé une fois le paiement confirmé par l'opérateur. Idempotent : sans effet si déjà fait."""
    pk = next((int(i['candidature']) for i in (payment.items or []) if isinstance(i, dict) and i.get('candidature')), None)
    if not pk:
        return
    with transaction.atomic():
        n = Candidature.objects.filter(pk=pk, statut='a_payer').update(
            statut='a_verifier', paiement=payment, updated_at=timezone.now())
        if n:
            c = Candidature.objects.get(pk=pk)
            _trace(c, "Paiement confirmé", 'Système')
            _ecrire(c, "Candidature reçue", "Nous avons bien reçu votre candidature et votre paiement. "
                                            "Nous la vérifions et revenons vers vous rapidement.")


def renvoyer(c):
    """Le candidat a corrigé son dossier : retour en vérification, sans repayer."""
    if c.statut == 'a_corriger':
        c.statut = 'a_verifier'
        c.save(update_fields=['statut', 'updated_at'])
        _trace(c, "Dossier corrigé et renvoyé", c.user)


def valider(c, auteur=''):
    """Crée (ou met à jour) la fiche Répétiteur visible dans l'appli."""
    with transaction.atomic():
        r = c.repetiteur or Repetiteur(nom=c.nom_complet)
        for champ in ('matieres', 'niveaux', 'ville', 'quartier', 'latitude', 'longitude', 'description',
                      'experience', 'tarif', 'whatsapp', 'email', 'telephone'):
            setattr(r, champ, getattr(c, champ))
        r.nom, r.actif, r.est_exemple = c.nom_complet, True, False
        if c.photo:
            c.photo.open('rb')
            r.photo.save(c.photo.name.rsplit('/', 1)[-1], ContentFile(c.photo.read()), save=False)
            c.photo.close()
        r.save()
        c.repetiteur, c.statut, c.motif, c.decide_le = r, 'validee', '', timezone.now()
        c.save(update_fields=['repetiteur', 'statut', 'motif', 'decide_le', 'updated_at'])
        _trace(c, "Validée : fiche publiée", auteur)
    _ecrire(c, "Candidature validée", "Votre candidature est validée : votre profil est maintenant visible "
                                      "dans l'application Lantante, rubrique « Répétiteur - École ».")
    return r


def demander_correction(c, motif, auteur=''):
    c.statut, c.motif = 'a_corriger', motif
    c.save(update_fields=['statut', 'motif', 'updated_at'])
    _trace(c, "Correction demandée", auteur, motif)
    _ecrire(c, "Candidature à corriger", f"Votre dossier doit être corrigé :\n{motif}\n\n"
                                         "Modifiez-le puis renvoyez-le, sans payer à nouveau.")


def rejeter(c, motif, auteur=''):
    c.statut, c.motif, c.decide_le = 'rejetee', motif, timezone.now()
    c.save(update_fields=['statut', 'motif', 'decide_le', 'updated_at'])
    if c.repetiteur_id:
        Repetiteur.objects.filter(pk=c.repetiteur_id).update(actif=False)
    _trace(c, "Rejetée", auteur, motif)
    _ecrire(c, "Candidature refusée", f"Votre candidature n'a pas été retenue :\n{motif}")


def purger_pieces(maintenant=None):
    """Supprime les pièces d'identité 90 jours après la décision finale. Renvoie le nombre de dossiers purgés."""
    limite = (maintenant or timezone.now()) - DELAI_PURGE
    n = 0
    for c in Candidature.objects.filter(statut__in=('validee', 'rejetee'), decide_le__lte=limite, pieces_supprimees=False):
        for f in (c.piece_recto, c.piece_verso):
            if f:
                f.delete(save=False)
        c.pieces_supprimees = True
        c.save(update_fields=['piece_recto', 'piece_verso', 'pieces_supprimees'])
        _trace(c, "Pièce d'identité supprimée (90 jours)", 'Système')
        n += 1
    return n
