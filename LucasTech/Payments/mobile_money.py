"""Mobile Money : pays et opérateurs pris en charge par FedaPay en paiement direct (sans redirection).

Le payeur choisit son pays et son opérateur sur le site et saisit son numéro une seule fois ; la demande
de paiement est envoyée directement sur son téléphone (il ne choisit plus rien chez FedaPay).
Codes des opérateurs = « modes » FedaPay (https://docs.fedapay.com/fr/payment-methods).
"""
import re

from django.core.exceptions import ValidationError

# pays -> libellé, indicatif, longueurs de numéro acceptées, opérateurs (mode FedaPay, libellé, préfixes connus)
COUNTRIES = {
    "tg": {"label": "Togo", "dial": "228", "digits": (8,), "example": "90 00 00 00", "operators": [
        ("togocel", "Mixx by Yas (ex T-Money)", ("70", "71", "72", "73", "90", "91", "92", "93")),
        ("moov_tg", "Moov Money", ("78", "79", "96", "97", "98", "99")),
    ]},
    "bj": {"label": "Bénin", "dial": "229", "digits": (8, 10), "example": "01 90 00 00 00", "operators": [
        ("mtn_open", "MTN MoMo", ()),
        ("moov", "Moov Money", ()),
        ("sbin", "Celtiis Cash", ()),
        ("bestcash", "BESTCASH Money", ()),
        ("coris", "Coris Money", ()),
    ]},
    "ci": {"label": "Côte d'Ivoire", "dial": "225", "digits": (10,), "example": "05 00 00 00 00", "operators": [
        ("mtn_ci", "MTN MoMo", ()),
        ("wave_ci", "Wave", ()),
    ]},
    "ne": {"label": "Niger", "dial": "227", "digits": (8,), "example": "90 00 00 00", "operators": [
        ("airtel_ne", "Airtel Money", ()),
    ]},
    "sn": {"label": "Sénégal", "dial": "221", "digits": (9,), "example": "76 000 00 00", "operators": [
        ("free_sn", "Free Money", ()),
    ]},
}
DEFAULT_COUNTRY = "tg"
COUNTRY_CODE = COUNTRIES[DEFAULT_COUNTRY]["dial"]  # compatibilité
COUNTRY_CHOICES = [(code, c["label"]) for code, c in COUNTRIES.items()]

OPERATORS = {mode: (country, label, prefixes)
             for country, c in COUNTRIES.items() for mode, label, prefixes in c["operators"]}
# Opérateurs que FedaPay n'accepte pas en paiement direct : le payeur termine sur la page FedaPay
# (numéro pré-rempli). Tous les autres reçoivent la demande directement sur le téléphone.
HOSTED_MODES = {"bestcash", "coris", "wave_ci"}
DIRECT_MODES = set(OPERATORS) - HOSTED_MODES
# Anciens codes (paiements CinetPay de l'historique), gardés pour l'affichage.
LEGACY_OPERATORS = [("TMONEY_TG", "T-Money"), ("MOOV_TG", "Moov Money")]
OPERATOR_CHOICES = [(mode, f"{label} ({COUNTRIES[c]['label']})") for mode, (c, label, _) in OPERATORS.items()] \
    + LEGACY_OPERATORS
USSD = {"togocel": "*145#", "moov_tg": "*155#"}

# Compatibilité (anciens noms)
TMONEY, MOOV = "togocel", "moov_tg"


def _digits(raw):
    digits = re.sub(r"\D", "", raw or "")
    return digits[2:] if digits.startswith("00") else digits


def normalize(raw, country=DEFAULT_COUNTRY):
    """« 92 96 77 87 », « 0022892967787 » ou « +228 92967787 » -> « +22892967787 » (selon le pays).
    Lève ValidationError si le numéro n'a pas la bonne longueur pour ce pays."""
    c = COUNTRIES.get(country)
    if not c:
        raise ValidationError("Pays non pris en charge.")
    digits = _digits(raw)
    if digits.startswith(c["dial"]) and len(digits) - len(c["dial"]) in c["digits"]:
        digits = digits[len(c["dial"]):]
    if len(digits) not in c["digits"]:
        n = " ou ".join(str(d) for d in c["digits"])
        raise ValidationError(
            f"Numéro invalide pour {c['label']} : saisissez les {n} chiffres de votre numéro Mobile Money, "
            f"ex. {c['example']}.")
    return f"+{c['dial']}{digits}"


def split(phone):
    """« +22892967787 » -> (« tg », « 92967787 »)."""
    digits = _digits(phone)
    for code, c in COUNTRIES.items():
        if digits.startswith(c["dial"]) and len(digits) - len(c["dial"]) in c["digits"]:
            return code, digits[len(c["dial"]):]
    return "", digits


def operator_for(phone):
    """Opérateur togolais deviné d'après le numéro (« togocel » / « moov_tg »), ou "" s'il n'est pas reconnu."""
    country, local = split(phone)
    for mode, (c, _label, prefixes) in OPERATORS.items():
        if c == country and prefixes and local[:2] in prefixes:
            return mode
    return ""


def check_operator(phone, country, mode):
    """Vérifie que l'opérateur existe dans ce pays et, quand on connaît ses préfixes, que le numéro lui appartient."""
    info = OPERATORS.get(mode)
    if not info or info[0] != country:
        raise ValidationError("Choisissez un opérateur disponible dans votre pays.")
    prefixes = info[2]
    if prefixes and split(phone)[1][:2] not in prefixes:
        guess = operator_for(phone)
        hint = f" Ce numéro semble être un numéro {OPERATORS[guess][1]}." if guess else ""
        raise ValidationError(f"Ce numéro n'est pas un numéro {info[1]}.{hint}")


def operator_label(code):
    if code in OPERATORS:
        return OPERATORS[code][1]
    return dict(LEGACY_OPERATORS).get(code, "")


def pretty(phone):
    """« +22892967787 » -> « +228 92 96 77 87 »."""
    country, local = split(phone)
    if not country:
        return phone or ""
    groups = [local[i:i + 2] for i in range(0, len(local), 2)]
    return f"+{COUNTRIES[country]['dial']} " + " ".join(groups)
