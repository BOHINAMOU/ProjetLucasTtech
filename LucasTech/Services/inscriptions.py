"""Validation des réponses au formulaire d'inscription d'un service (côté serveur, jamais de confiance au client)."""
import re
from datetime import date

from django.core.exceptions import ValidationError


def valider(service, donnees, pays='tg'):
    """Renvoie (réponses nettoyées {libellé: valeur}, erreurs {id du champ: message})."""
    from Payments.mobile_money import normalize
    rep, err = {}, {}
    for c in service.champs.all():
        v = donnees.get(str(c.pk), donnees.get(c.libelle, ''))
        v = '' if v is None else str(v).strip()
        if not v:
            if c.obligatoire:
                err[str(c.pk)] = "Obligatoire."
            continue
        if len(v) > (2000 if c.type == 'long' else 200):
            err[str(c.pk)] = "Trop long."
        elif c.type == 'nombre' and not re.fullmatch(r"-?\d+([.,]\d+)?", v):
            err[str(c.pk)] = "Nombre attendu."
        elif c.type == 'email' and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            err[str(c.pk)] = "E-mail invalide."
        elif c.type == 'telephone':
            try:
                v = normalize(v, pays)
            except ValidationError as e:
                err[str(c.pk)] = e.messages[0]
        elif c.type == 'date':
            try:
                v = date.fromisoformat(v[:10]).isoformat()
            except ValueError:
                err[str(c.pk)] = "Date invalide."
        elif c.type == 'choix' and v not in c.options():
            err[str(c.pk)] = "Choix invalide."
        rep[c.libelle] = v
    return rep, err
