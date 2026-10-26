"""Contenu de la page « Monétisation » et contrôle du numéro de téléphone du formulaire."""
import re

try:
    import phonenumbers
except ImportError:  # sécurité : sans la bibliothèque, on se contente d'un contrôle de longueur
    phonenumbers = None

# Réseaux présentés sur la page (icônes Font Awesome « brands », couleurs officielles des marques).
# Les conditions exactes changent selon le pays et la période : on décrit ce qui est généralement demandé,
# l'équipe vérifie les règles en vigueur pour chaque personne.
PLATFORMS = [
    {
        'key': 'facebook', 'name': 'Facebook', 'icon': 'fa-facebook-f', 'color': '#1877f2',
        'earn': "Publicités dans les vidéos et les Reels, bonus pour créateurs, abonnements de fans, étoiles offertes par le public.",
        'needs': "Une Page ou un profil en mode professionnel, du contenu original, une audience régulière et le respect des règles de monétisation.",
    },
    {
        'key': 'tiktok', 'name': 'TikTok', 'icon': 'fa-tiktok', 'color': '#111111',
        'earn': "Programme de récompenses des créateurs, cadeaux pendant les lives, abonnements, partenariats avec des marques.",
        'needs': "Un âge minimum, un nombre d'abonnés et de vues suffisant, des vidéos originales. Tous les pays ne sont pas éligibles : nous vérifions le vôtre.",
    },
    {
        'key': 'youtube', 'name': 'YouTube', 'icon': 'fa-youtube', 'color': '#ff0000',
        'earn': "Publicités (Programme Partenaire YouTube), abonnements de la chaîne, Super Chat et Shorts.",
        'needs': "Un nombre d'abonnés, des heures de visionnage ou des vues de Shorts, du contenu original et un compte de paiement AdSense.",
    },
    {
        'key': 'instagram', 'name': 'Instagram', 'icon': 'fa-instagram', 'color': '#e4405f',
        'earn': "Cadeaux, abonnements, bonus selon les programmes ouverts et partenariats rémunérés avec des marques.",
        'needs': "Un compte professionnel ou créateur, une audience engagée, du contenu original et un pays où les outils sont ouverts.",
    },
    {
        'key': 'whatsapp', 'name': 'WhatsApp', 'icon': 'fa-whatsapp', 'color': '#25d366',
        'earn': "Vente de produits et de services, chaîne WhatsApp, communauté et partenariats grâce à votre audience.",
        'needs': "Un compte WhatsApp Business bien configuré, un catalogue clair et une communauté qui vous fait confiance.",
    },
    {
        'key': 'x', 'name': 'X (Twitter)', 'icon': 'fa-x-twitter', 'color': '#111111',
        'earn': "Partage des revenus publicitaires, abonnements de fans et pourboires.",
        'needs': "Un abonnement premium, un nombre d'abonnés et d'impressions suffisant, et un compte en règle.",
    },
    {
        'key': 'snapchat', 'name': 'Snapchat', 'icon': 'fa-snapchat', 'color': '#f2c400',
        'earn': "Programmes de récompenses pour les créateurs, selon leur disponibilité, et partenariats avec des marques.",
        'needs': "Un profil public, des contenus réguliers et originaux, et un pays éligible.",
    },
    {
        'key': 'telegram', 'name': 'Telegram', 'icon': 'fa-telegram', 'color': '#26a5e4',
        'earn': "Revenus publicitaires des chaînes, abonnements payants, promotion de produits.",
        'needs': "Une chaîne avec une audience suffisante et un contenu régulier.",
    },
    {
        'key': 'linkedin', 'name': 'LinkedIn', 'icon': 'fa-linkedin-in', 'color': '#0a66c2',
        'earn': "Missions et clients grâce à votre expertise, newsletters, partenariats professionnels.",
        'needs': "Un profil complet et crédible, des publications régulières et un réseau actif.",
    },
    {
        'key': 'twitch', 'name': 'Twitch', 'icon': 'fa-twitch', 'color': '#9146ff',
        'earn': "Abonnements, dons, bits et publicités pendant vos directs.",
        'needs': "Un nombre minimum d'heures de direct, de spectateurs et d'abonnés (Programme Affilié).",
    },
    {
        'key': 'pinterest', 'name': 'Pinterest', 'icon': 'fa-pinterest-p', 'color': '#e60023',
        'earn': "Trafic vers votre site ou votre boutique et partenariats de marque.",
        'needs': "Un compte professionnel et des épingles originales publiées régulièrement.",
    },
]

# Choix proposés dans le formulaire (les mêmes réseaux + « Autre »)
PLATFORM_CHOICES = [p['name'] for p in PLATFORMS] + ['Autre']

STEPS = [
    ('fa-magnifying-glass-chart', "Analyse de votre compte",
     "Nous regardons où vous en êtes : audience, contenu, pays, règles de la plateforme."),
    ('fa-user-plus', "Création ou mise en place du compte",
     "Nous vous aidons à créer un compte propre et complet, avec les bons réglages dès le départ."),
    ('fa-list-check', "Atteindre les critères",
     "Plan de contenu, rythme de publication et bonnes pratiques pour remplir les conditions de la plateforme."),
    ('fa-paper-plane', "Demande de monétisation",
     "Nous préparons avec vous la demande et vous guidons jusqu'à la réponse de la plateforme."),
    ('fa-sack-dollar', "Premiers revenus",
     "Configuration du paiement et conseils pour faire grandir vos revenus dans la durée."),
]

WHATSAPP_WAYS = [
    ('fa-store', "WhatsApp Business", "Catalogue de produits, réponses automatiques, commandes et suivi des clients."),
    ('fa-bullhorn', "Chaîne WhatsApp", "Diffusez vos contenus à une large audience et transformez-la en clients ou en partenaires."),
    ('fa-people-group', "Communautés et groupes", "Réunissez des clients autour de vos offres, de vos formations ou de vos conseils."),
    ('fa-handshake', "Partenariats", "Les marques paient pour toucher une audience qui vous suit et vous fait confiance."),
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
