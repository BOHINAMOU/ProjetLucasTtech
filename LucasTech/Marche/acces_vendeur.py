"""Période d'accès des vendeurs : durées rapides, suspendre / réactiver, expiration automatique et rappels.

Aucune donnée n'est supprimée : seul le statut (et la date de fin) change.
"""
import calendar
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

DUREES = [('1', "1 mois"), ('3', "3 mois"), ('6', "6 mois"), ('12', "1 an"), ('illimite', "Sans limite"), ('date', "Date libre")]


def plus_mois(d, n):
    m = d.month - 1 + n
    a, m = d.year + m // 12, m % 12 + 1
    return d.replace(year=a, month=m, day=min(d.day, calendar.monthrange(a, m)[1]))


def fin_pour(duree, date_libre=None, depuis=None):
    """Date de fin pour une durée rapide ('1', '3', '6', '12'), None pour « sans limite », ou la date libre."""
    depuis = depuis or timezone.localdate()
    if duree == 'illimite':
        return None
    if duree == 'date':
        return date_libre
    return plus_mois(depuis, int(duree))


def suspendre(v):
    v.statut = 'suspendu'
    v.save(update_fields=['statut'])


def reactiver(v, fin):
    """Remet le vendeur actif jusqu'à `fin` (None = sans limite). Tout revient comme avant."""
    v.statut, v.fin_acces = 'valide', fin
    if not v.debut_acces:
        v.debut_acces = timezone.localdate()
    v.save(update_fields=['statut', 'fin_acces', 'debut_acces'])


def _site():
    return (getattr(settings, 'SITE_URL', '') or 'https://lantantetechnologie.com').rstrip('/')


def verifier_tous(aujourdhui=None):
    """Tâche quotidienne : passe en « Expiré » les accès terminés, prévient 7 jours et 1 jour avant.
    Renvoie (nb_expirés, nb_rappels)."""
    from .models import Vendeur
    t = aujourdhui or timezone.localdate()
    expires = 0
    for v in Vendeur.objects.filter(statut='valide', fin_acces__lt=t).select_related('user'):
        v.statut = 'expire'
        v.save(update_fields=['statut'])
        expires += 1
        _ecrire(v, "Votre accès vendeur Lantante est terminé",
                f"Bonjour,\n\nL'accès de votre boutique « {v.boutique} » s'est terminé le {v.fin_acces:%d/%m/%Y}.\n\n"
                "Vos produits et vos commandes sont conservés. Contactez Lantante pour le prolonger.\n\nL'équipe Lantante")
    rappels = 0
    for jours in (7, 1):
        for v in Vendeur.objects.filter(statut='valide', fin_acces=t + timedelta(days=jours)).select_related('user'):
            rappels += 1
            quand = "demain" if jours == 1 else f"dans {jours} jours"
            _ecrire(v, f"Votre accès vendeur se termine {quand}",
                    f"Bonjour,\n\nL'accès de votre boutique « {v.boutique} » se termine {quand}, le {v.fin_acces:%d/%m/%Y}.\n\n"
                    f"Contactez Lantante pour le prolonger.\n\nVotre espace : {_site()}{v.lien_espace()}\n\nL'équipe Lantante")
    return expires, rappels


def _ecrire(v, sujet, texte):
    if not v.user.email:
        return
    try:
        send_mail(sujet, texte, settings.DEFAULT_FROM_EMAIL, [v.user.email], fail_silently=True)
    except Exception:
        pass
