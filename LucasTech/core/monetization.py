"""Contenu de la page « Monétisation » et contrôle du numéro de téléphone du formulaire."""
import re

try:
    import phonenumbers
except ImportError:  # sécurité : sans la bibliothèque, on se contente d'un contrôle de longueur
    phonenumbers = None

# Réseaux présentés sur la page (icônes Font Awesome « brands », couleurs officielles des marques).
# Le détail des conditions n'est pas affiché : l'équipe l'explique à chaque personne qui la contacte.
PLATFORMS = [
    {
        'key': 'facebook', 'name': 'Facebook', 'icon': 'fa-facebook-f', 'color': '#1877f2',
    },
    {
        'key': 'tiktok', 'name': 'TikTok', 'icon': 'fa-tiktok', 'color': '#111111',
    },
    {
        'key': 'youtube', 'name': 'YouTube', 'icon': 'fa-youtube', 'color': '#ff0000',
    },
    {
        'key': 'instagram', 'name': 'Instagram', 'icon': 'fa-instagram', 'color': '#e4405f',
    },
    {
        'key': 'whatsapp', 'name': 'WhatsApp', 'icon': 'fa-whatsapp', 'color': '#25d366',
    },
    {
        'key': 'x', 'name': 'X (Twitter)', 'icon': 'fa-x-twitter', 'color': '#111111',
    },
    {
        'key': 'snapchat', 'name': 'Snapchat', 'icon': 'fa-snapchat', 'color': '#f2c400',
    },
    {
        'key': 'telegram', 'name': 'Telegram', 'icon': 'fa-telegram', 'color': '#26a5e4',
    },
    {
        'key': 'linkedin', 'name': 'LinkedIn', 'icon': 'fa-linkedin-in', 'color': '#0a66c2',
    },
    {
        'key': 'twitch', 'name': 'Twitch', 'icon': 'fa-twitch', 'color': '#9146ff',
    },
    {
        'key': 'pinterest', 'name': 'Pinterest', 'icon': 'fa-pinterest-p', 'color': '#e60023',
    },
]

# Choix proposés dans le formulaire (les mêmes réseaux + « Autre »)
PLATFORM_CHOICES = [p['name'] for p in PLATFORMS] + ['Autre']

STEPS = [
    ('fa-magnifying-glass-chart', "Analyse de votre compte"),
    ('fa-user-plus', "Création ou mise en place du compte"),
    ('fa-list-check', "Atteindre les critères"),
    ('fa-paper-plane', "Demande de monétisation"),
    ('fa-sack-dollar', "Premiers revenus"),
]

WHATSAPP_WAYS = [
    ('fa-store', "WhatsApp Business"),
    ('fa-bullhorn', "Chaîne WhatsApp"),
    ('fa-people-group', "Communautés"),
    ('fa-handshake', "Partenariats"),
]


def clean_phone(dial_code, raw):
    """Retourne (numéro nettoyé, None) ou (None, message d'erreur) pour un numéro saisi avec son indicatif."""
    raw = (raw or '').strip()
    if not raw:
        return None, "Le numéro de téléphone est requis."
    if re.search(r'[^\d\s.\-()+]', raw):
        return None, "Le numéro ne doit contenir que des chiffres."
    digits = re.sub(r'\D', '', raw)
    dial = re.sub(r'\D', '', dial_code or '')
    if not dial:
        return None, "Choisissez l'indicatif de votre pays."

    candidates = [digits]
    if (raw.startswith('+') or raw.startswith('00')) and digits.lstrip('0').startswith(dial):
        candidates.append(digits.lstrip('0')[len(dial):])  # l'indicatif a été retapé dans le numéro
    if digits.startswith('0'):
        candidates.insert(0, digits[1:])                    # zéro initial local (ex : 06 12 …), essayé en premier
    candidates = [c for c in dict.fromkeys(candidates) if c]

    if phonenumbers is None:
        return (candidates[0], None) if 6 <= len(candidates[0]) <= 14 else (None, "Numéro de téléphone invalide.")
    for cand in candidates:
        try:
            number = phonenumbers.parse(f'+{dial}{cand}', None)
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_valid_number(number):
            e164 = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
            return e164[1 + len(dial):], None  # numéro national canonique, sans indicatif
    return None, "Ce numéro n'est pas valide pour l'indicatif choisi. Vérifiez-le."
