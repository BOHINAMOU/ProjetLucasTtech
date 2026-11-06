"""Petit client de l'API FedaPay (https://docs.fedapay.com).

Réglages (.env) :
    FEDAPAY_SECRET_KEY   sk_sandbox_... (test) ou sk_live_... (réel)
    FEDAPAY_ENV          sandbox (par défaut) ou live

Sans clé secrète, le site passe en « mode démo » en local (DEBUG) : une page
simule le paiement, pour pouvoir tout tester. En production sans clé, le
paiement en ligne est simplement désactivé (le bouton WhatsApp reste).
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_BASE = {
    'sandbox': 'https://sandbox-api.fedapay.com/v1',
    'live': 'https://api.fedapay.com/v1',
}
PAID_STATUSES = {'approved', 'transferred'}
FAILED_STATUSES = {'declined', 'canceled', 'refunded'}


class FedaPayError(Exception):
    pass


def secret_key():
    return getattr(settings, 'FEDAPAY_SECRET_KEY', '') or ''


def environment():
    env = (getattr(settings, 'FEDAPAY_ENV', '') or 'sandbox').lower()
    return env if env in API_BASE else 'sandbox'


def is_configured():
    return bool(secret_key())


def mode():
    """'live', 'sandbox', 'demo' (local sans clé) ou '' (désactivé)."""
    if is_configured():
        return environment()
    return 'demo' if settings.DEBUG else ''


def is_enabled():
    return bool(mode())


def _headers():
    return {'Authorization': f'Bearer {secret_key()}', 'Content-Type': 'application/json',
            'Accept': 'application/json'}


def _unwrap(data, key='v1/transaction'):
    if isinstance(data, dict) and key in data:
        return data[key]
    return data


def _phone(phone):
    """Numéro au format FedaPay {number, country}, ou None si illisible."""
    try:
        import phonenumbers
        num = phonenumbers.parse(phone, 'TG')
        if not phonenumbers.is_valid_number(num):
            return None
        region = phonenumbers.region_code_for_number(num)
        return {'number': str(num.national_number), 'country': region.lower()}
    except Exception:
        return None


def create_transaction(payment, callback_url):
    """Crée la transaction et renvoie (id, url de paiement)."""
    base = API_BASE[environment()]
    customer = {'firstname': payment.first_name, 'lastname': payment.last_name, 'email': payment.email}
    phone = _phone(payment.phone)
    if phone:
        customer['phone_number'] = phone
    body = {
        'description': f'{payment.description} [{payment.reference}]'[:250],
        'amount': int(payment.amount),
        'currency': {'iso': 'XOF'},
        'callback_url': callback_url,
        'customer': customer,
    }
    try:
        r = requests.post(f'{base}/transactions', json=body, headers=_headers(), timeout=25)
        if r.status_code >= 400 and 'phone_number' in customer:
            # Numéro refusé par FedaPay : on réessaie sans (le client le saisira sur la page de paiement).
            customer.pop('phone_number')
            r = requests.post(f'{base}/transactions', json=body, headers=_headers(), timeout=25)
        r.raise_for_status()
        tx = _unwrap(r.json())
        tx_id = tx['id']
        t = requests.post(f'{base}/transactions/{tx_id}/token', headers=_headers(), timeout=25)
        t.raise_for_status()
        url = t.json().get('url')
        if not url:
            raise FedaPayError('Lien de paiement absent de la réponse FedaPay.')
        return str(tx_id), url
    except (requests.RequestException, KeyError, ValueError) as exc:
        detail = getattr(getattr(exc, 'response', None), 'text', '')[:500]
        logger.error('FedaPay create_transaction failed for %s: %s %s', payment.reference, exc, detail)
        raise FedaPayError(str(exc)) from exc


def transaction_status(tx_id):
    """Statut réel d'une transaction, lu directement chez FedaPay (jamais depuis le navigateur)."""
    base = API_BASE[environment()]
    try:
        r = requests.get(f'{base}/transactions/{tx_id}', headers=_headers(), timeout=20)
        r.raise_for_status()
        return (_unwrap(r.json()).get('status') or '').lower()
    except (requests.RequestException, ValueError, AttributeError) as exc:
        logger.error('FedaPay transaction_status failed for %s: %s', tx_id, exc)
        return ''
