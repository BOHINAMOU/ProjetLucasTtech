"""Connexion à l'administration en deux étapes : mot de passe, puis code à 6 chiffres reçu par e-mail.

- Le code n'est jamais stocké en clair (empreinte HMAC) ni écrit dans les journaux.
- Valable 10 min, 5 essais au plus, renvoi limité (3 par 10 min).
- « Se souvenir de cet appareil » : cookie signé 30 jours, lié au mot de passe actuel (changer le mot de passe l'annule).
- Activation : variable d'environnement ADMIN_2FA=1. Secours : `manage.py deux_facteurs desactiver <email>`.
"""
import hashlib
import hmac
import logging
import os
import secrets

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail

log = logging.getLogger('lantante.2fa')

DUREE = 10 * 60
ESSAIS = 5
RENVOIS = 3
COOKIE = 'lt_appareil'
COOKIE_JOURS = 30


def active():
    return os.environ.get('ADMIN_2FA', '') == '1'


def exempte(user):
    from .models import Exemption2FA
    return Exemption2FA.objects.filter(user=user).exists()


def requise(user):
    return active() and user.is_staff and not exempte(user)


def _empreinte(uid, code):
    return hmac.new(settings.SECRET_KEY.encode(), f'{uid}:{code}'.encode(), hashlib.sha256).hexdigest()


def envoyer_code(user):
    """Envoie un nouveau code. Renvoie False si trop de renvois récents."""
    cle_r = f'2fa:renvois:{user.pk}'
    n = cache.get(cle_r, 0)
    if n >= RENVOIS:
        return False
    cache.set(cle_r, n + 1, DUREE)
    code = f'{secrets.randbelow(10 ** 6):06d}'
    cache.set(f'2fa:code:{user.pk}', {'h': _empreinte(user.pk, code), 'essais': 0}, DUREE)
    send_mail("Votre code de connexion Lantante",
              f"Bonjour,\n\nVotre code de connexion à l'administration Lantante : {code}\n\n"
              f"Il est valable 10 minutes. Si vous n'êtes pas à l'origine de cette connexion, changez votre mot de passe.\n\n"
              f"L'équipe Lantante", None, [user.email])
    log.info("2FA : code envoyé au compte %s", user.pk)
    return True


def verifier(user, code):
    """(ok, message)."""
    cle = f'2fa:code:{user.pk}'
    d = cache.get(cle)
    if not d:
        return False, "Code expiré. Demandez un nouveau code."
    if d['essais'] >= ESSAIS:
        cache.delete(cle)
        return False, "Trop d'essais. Demandez un nouveau code."
    code = ''.join(c for c in str(code or '') if c.isdigit())
    if len(code) == 6 and hmac.compare_digest(d['h'], _empreinte(user.pk, code)):
        cache.delete(cle)
        cache.delete(f'2fa:renvois:{user.pk}')
        log.info("2FA : connexion validée pour le compte %s", user.pk)
        return True, ''
    d['essais'] += 1
    cache.set(cle, d, DUREE)
    log.warning("2FA : code erroné pour le compte %s (%s essai(s))", user.pk, d['essais'])
    reste = ESSAIS - d['essais']
    return False, f"Code incorrect. {reste} essai(s) restant(s)." if reste > 0 else "Trop d'essais. Demandez un nouveau code."


def _jeton_appareil(user):
    return signing.dumps({'u': user.pk, 'p': user.password[-12:]}, salt='lt-2fa-appareil')


def appareil_connu(request, user):
    v = request.COOKIES.get(COOKIE)
    if not v:
        return False
    try:
        d = signing.loads(v, salt='lt-2fa-appareil', max_age=COOKIE_JOURS * 86400)
    except signing.BadSignature:
        return False
    return d.get('u') == user.pk and d.get('p') == user.password[-12:]


def retenir_appareil(response, user):
    response.set_cookie(COOKIE, _jeton_appareil(user), max_age=COOKIE_JOURS * 86400, secure=not settings.DEBUG,
                        httponly=True, samesite='Lax')
