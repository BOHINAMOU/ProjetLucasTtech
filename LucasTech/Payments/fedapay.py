"""Client de l'API FedaPay (https://docs.fedapay.com), sur le modèle de FESCOSLAM.

Paiement direct, sans quitter le site :
  1. POST /v1/transactions (merchant_reference = notre référence)
  2. POST /v1/transactions/<id>/token
  3. POST /v1/<opérateur> {token, phone_number} -> la demande arrive sur le téléphone du client
  4. GET /v1/transactions/<id> -> statut, toujours relu côté serveur avant de livrer quoi que ce soit.

Réglages (.env) : FEDAPAY_SECRET_KEY, FEDAPAY_ENV (sandbox | live).
Sans clé : « mode démo » en local (DEBUG), paiement désactivé en production.
"""
import logging
import re

import requests
from django.conf import settings

from . import mobile_money

logger = logging.getLogger(__name__)

API_BASE = {
    'sandbox': 'https://sandbox-api.fedapay.com/v1',
    'live': 'https://api.fedapay.com/v1',
}
PAID_STATUSES = {'approved', 'transferred'}
FAILED_STATUSES = {'declined', 'canceled', 'expired', 'refunded'}


class FedaPayError(Exception):
    def __init__(self, message, detail='', status=None):
        super().__init__(message)
        self.detail = detail
        self.status = status


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


def _amount_message(text):
    numbers = re.findall(r'\d+', text)
    if 'maximum' in text.lower() and numbers:
        limit = f"{int(numbers[-1]):,}".replace(',', ' ')
        return (f"Ce montant dépasse le plafond autorisé par paiement en ligne ({limit} FCFA pour le moment). "
                "Contactez-nous sur WhatsApp pour finaliser votre achat.")
    if 'minimum' in text.lower() and numbers:
        limit = f"{int(numbers[-1]):,}".replace(',', ' ')
        return f"Le montant minimum par paiement est de {limit} FCFA."
    return "Ce montant n'est pas accepté par le service de paiement."


def _call(method, path, data=None):
    url = API_BASE[environment()] + path
    headers = {'Authorization': f'Bearer {secret_key()}', 'Accept': 'application/json',
               'Content-Type': 'application/json', 'User-Agent': 'LantanteTechnologie/1.0 (Django)'}
    try:
        r = requests.request(method, url, json=data, headers=headers, timeout=30)
    except requests.Timeout as exc:
        logger.error('FedaPay %s %s : délai dépassé', method, path)
        raise FedaPayError("Le service de paiement met trop de temps à répondre. Réessayez dans un instant.") from exc
    except requests.RequestException as exc:
        logger.error('FedaPay %s %s : %s', method, path, exc)
        raise FedaPayError("Le service de paiement est momentanément indisponible.") from exc
    if r.status_code >= 400:
        detail, errors = '', {}
        try:
            body = r.json()
            detail = str(body.get('message', ''))[:200]
            errors = body.get('errors') if isinstance(body.get('errors'), dict) else {}
        except ValueError:
            pass
        logger.error('FedaPay %s %s -> HTTP %s %s %s', method, path, r.status_code, detail, errors)
        amount_errors = errors.get('amount') or []
        if r.status_code == 400 and amount_errors:
            raise FedaPayError(_amount_message(str(amount_errors[0])), detail, r.status_code)
        raise FedaPayError("Le service de paiement est momentanément indisponible.", detail, r.status_code)
    try:
        return r.json()
    except ValueError:
        return {}


def _transaction(result):
    if isinstance(result, dict):
        tx = result.get('v1/transaction') or result.get('transaction')
        if isinstance(tx, dict):
            return tx
        if 'status' in result or 'id' in result:
            return result
    return {}


def _customer(payment):
    customer = {'firstname': (payment.first_name or 'Client')[:100],
                'lastname': (payment.last_name or 'Lantante')[:100]}
    if payment.email:
        customer['email'] = payment.email
    country, local = mobile_money.split(payment.phone)
    if country:
        customer['phone_number'] = {'number': '+' + mobile_money.COUNTRIES[country]['dial'] + local,
                                    'country': country}
    return customer


def start(payment, callback_url):
    """Lance le paiement. Renvoie None si la demande est partie directement sur le téléphone
    (le client attend sur le site), sinon l'URL de la page FedaPay (opérateurs sans paiement direct)."""
    result = _call('POST', '/transactions', {
        'description': f'{payment.description} [{payment.reference}]'[:250],
        'amount': int(payment.amount),
        'currency': {'iso': 'XOF'},
        'callback_url': callback_url,
        'merchant_reference': payment.reference,
        'custom_metadata': {'reference': payment.reference, 'kind': payment.kind},
        'customer': _customer(payment),
    })
    tx = _transaction(result)
    if not tx.get('id'):
        raise FedaPayError("Le paiement n'a pas pu être lancé. Réessayez dans un instant.")
    payment.fedapay_id = str(tx['id'])
    payment.save(update_fields=['fedapay_id'])
    token = _call('POST', f"/transactions/{tx['id']}/token") or {}
    if payment.operator in mobile_money.DIRECT_MODES and token.get('token'):
        country, local = mobile_money.split(payment.phone)
        try:
            _call('POST', '/' + payment.operator,
                  {'token': token['token'], 'phone_number': {'number': local, 'country': country.upper()}})
        except FedaPayError as exc:
            if exc.status and 400 <= exc.status < 500:
                raise FedaPayError(
                    f"{mobile_money.operator_label(payment.operator)} n'a pas accepté la demande pour le "
                    f"{mobile_money.pretty(payment.phone)}. Vérifiez le numéro et l'opérateur, puis réessayez.",
                    exc.detail, exc.status) from exc
            raise
        return None
    url = token.get('url')
    if not url:
        raise FedaPayError("Le paiement n'a pas pu être lancé. Réessayez dans un instant.")
    payment.payment_url = url
    payment.save(update_fields=['payment_url'])
    return url


def transaction_status(payment):
    """'approved' seulement si la transaction est bien la nôtre et du bon montant."""
    try:
        tx = _transaction(_call('GET', f'/transactions/{payment.fedapay_id}'))
    except FedaPayError:
        return ''
    status = str(tx.get('status') or '').lower()
    if status in PAID_STATUSES:
        same_ref = (tx.get('merchant_reference') or payment.reference) == payment.reference
        same_amount = str(tx.get('amount', '')) == str(payment.amount)
        if not (same_ref and same_amount):
            logger.error('FedaPay : transaction %s incohérente avec %s', tx.get('id'), payment.reference)
            return 'pending'
    return status
