"""Notifications push vers les téléphones (Expo Push). Envoi en arrière-plan : n'a jamais le droit de bloquer ni de casser une action."""
import logging
import threading

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
EXPO_PUSH_URL = 'https://exp.host/--/api/v2/push/send'


def send_push(user, title, body, url=''):
    """Envoie une notification à tous les téléphones enregistrés de l'utilisateur (désactivé hors production)."""
    if not getattr(settings, 'PUSH_ENABLED', False):
        return
    tokens = list(user.device_tokens.values_list('token', flat=True))
    if not tokens:
        return
    payload = [{'to': token, 'title': title, 'body': body[:180], 'sound': 'default', 'data': {'url': url}}
               for token in tokens]

    def _send():
        try:
            requests.post(EXPO_PUSH_URL, json=payload, timeout=8,
                          headers={'Accept': 'application/json', 'Accept-Encoding': 'gzip, deflate'})
        except Exception:  # un téléphone injoignable ne doit jamais gêner le site
            logger.warning("Échec d'envoi de la notification push", exc_info=True)

    threading.Thread(target=_send, daemon=True).start()
