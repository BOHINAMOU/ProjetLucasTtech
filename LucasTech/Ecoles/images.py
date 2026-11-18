"""Image par défaut d'une filière selon son domaine (photos libres de droits CC0), pour qu'aucune carte ne reste vide."""
import unicodedata

from django.templatetags.static import static

# (mots-clés sans accents, image) : le premier qui correspond gagne
DOMAINES = [
    (('architect',), 'architecture'),
    (('urbanis', 'amenagement', 'territoire'), 'urbanisme'),
    (('gestion urbaine', 'ville', 'mobilite'), 'ville'),
    (('transit', 'douane', 'portuaire'), 'port'),
    (('transport', 'logisti'), 'logistique'),
    (('geometre', 'topograph'), 'topographie'),
    (('genie civil', 'ouvrage', 'btp', 'batiment', 'construction'), 'btp'),
    ((' eau', 'assainissement', 'dechet', 'environnement'), 'chantier'),
    (('electromecan', 'mecani', 'industri', 'maintenance indus'), 'electrotechnique'),
    (('electri', 'electrotech'), 'electricite'),
    (('energie', 'solaire', 'renouvelable'), 'energie'),
    (('intelligence artificielle', ' ia ', 'machine learning'), 'ia'),
    (('donnee', 'data', 'statisti'), 'donnees'),
    (('reseau', 'telecom', 'securite informatique', 'cyber'), 'reseaux'),
    (('informati', 'logiciel', 'developpe', 'programm', 'systeme', 'numerique', 'technologies'), 'informatique'),
    (('droit', 'juridi', 'marches publics'), 'droit'),
    (('communication', 'journalis', 'media', 'marketing', 'publicite'), 'medias'),
    (('tourisme', 'hotel'), 'tourisme'),
    (('sante', 'medecine', 'infirm', 'pharma', 'sage-femme'), 'sante'),
    (('agro', 'agricult', 'elevage'), 'agronomie'),
    (('lettre', 'langue', 'anglais', 'philosoph', 'histoire', 'sociolog'), 'lettres'),
    (('education', 'enseign', 'pedagog'), 'education'),
    (('mba', 'management', 'administration', 'ressources humaines', 'assistant', 'direction'), 'management'),
    (('compta', 'finance', 'banque', 'audit', 'controle', 'assurance'), 'economie'),
    (('econom', 'gestion', 'commerce', 'affaires'), 'gestion'),
]


def _simple(t):
    t = unicodedata.normalize('NFKD', t or '').encode('ascii', 'ignore').decode().lower()
    return f' {t} '


def domaine(nom):
    t = _simple(nom)
    for mots, image in DOMAINES:
        if any(m in t for m in mots):
            return image
    return 'defaut'


def image_domaine(request, nom):
    chemin = f'ecoles/domaines/{domaine(nom)}.webp'
    try:
        url = static(chemin)
    except ValueError:  # manifeste absent (tests, avant collectstatic)
        from django.conf import settings
        url = settings.STATIC_URL + chemin
    return request.build_absolute_uri(url) if request else url
