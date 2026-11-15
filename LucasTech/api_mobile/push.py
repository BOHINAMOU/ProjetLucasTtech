"""Notifications push via Firebase Cloud Messaging (API HTTP v1).

La clé du compte de service est hors du dépôt : chemin dans FIREBASE_SA_PATH (.env). Sans clé, rien n'est envoyé
et rien n'échoue : la cloche dans l'appli continue de fonctionner.
"""
import json
import logging
import os
import threading
import time

import requests
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)
SCOPE = 'https://www.googleapis.com/auth/firebase.messaging'
_jeton = {'valeur': None, 'expire': 0}
_verrou = threading.Lock()


def _cle():
    chemin = getattr(settings, 'FIREBASE_SA_PATH', '') or os.environ.get('FIREBASE_SA_PATH', '')
    if not chemin or not os.path.isfile(chemin):
        return None
    try:
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        logger.warning("Clé Firebase illisible : %s", chemin)
        return None


def actif():
    return _cle() is not None


def _access_token(cle):
    with _verrou:
        if _jeton['valeur'] and _jeton['expire'] > time.time() + 60:
            return _jeton['valeur']
        import jwt
        maintenant = int(time.time())
        assertion = jwt.encode({'iss': cle['client_email'], 'scope': SCOPE, 'aud': cle['token_uri'],
                                'iat': maintenant, 'exp': maintenant + 3600}, cle['private_key'], algorithm='RS256')
        r = requests.post(cle['token_uri'], data={'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                                                  'assertion': assertion}, timeout=15)
        r.raise_for_status()
        d = r.json()
        _jeton['valeur'], _jeton['expire'] = d['access_token'], maintenant + int(d.get('expires_in', 3600))
        return _jeton['valeur']


def destinataires(notification):
    from django.contrib.auth import get_user_model
    from .models import Appareil
    n = notification
    qs = Appareil.objects.all()
    if n.audience == 'personne':
        qs = qs.filter(user_id=n.utilisateur_id)
    elif n.audience == 'groupe':
        qs = qs.filter(user__in=get_user_model().objects.filter(groups=n.groupe_id))
    return qs


def envoyer(notification):
    """Envoie la notification à tous les téléphones concernés. Retourne le nombre d'envois réussis."""
    from .models import Appareil
    cle = _cle()
    if not cle:
        return 0
    try:
        token = _access_token(cle)
    except Exception:
        logger.exception("Jeton Firebase impossible")
        return 0
    n = notification
    url = f"https://fcm.googleapis.com/v1/projects/{cle['project_id']}/messages:send"
    data = {'notif_id': str(n.pk), 'cible': n.cible or '', 'cible_id': str(n.cible_id or ''), 'lien': n.lien or ''}
    ok = 0
    for a in list(destinataires(n).only('pk', 'jeton')):
        msg = {'message': {'token': a.jeton, 'notification': {'title': n.titre, 'body': n.message[:240]},
                           'data': data, 'android': {'priority': 'high', 'notification': {'sound': 'default'}}}}
        try:
            r = requests.post(url, json=msg, headers={'Authorization': f'Bearer {token}'}, timeout=15)
        except requests.RequestException:
            logger.warning("FCM injoignable")
            break
        if r.status_code == 200:
            ok += 1
        elif r.status_code in (404, 400) and ('UNREGISTERED' in r.text or 'INVALID_ARGUMENT' in r.text):
            Appareil.objects.filter(pk=a.pk).delete()  # appli désinstallée ou jeton périmé
        else:
            logger.warning("FCM %s : %s", r.status_code, r.text[:200])
    return ok


def apres_creation(notification):
    """Envoi en arrière-plan une fois la notification enregistrée (n'alourdit pas la requête)."""
    if not actif():
        return
    pk = notification.pk

    def lancer():
        from .models import Notification

        def tache():
            try:
                n = Notification.objects.filter(pk=pk).first()
                if n:
                    envoyer(n)
            except Exception:
                logger.exception("Envoi push impossible")
            finally:
                from django.db import connection
                connection.close()

        threading.Thread(target=tache, daemon=True).start()

    transaction.on_commit(lancer)
