"""Donne une photo à chaque filière qui n'en a pas, selon son domaine (photos CC0 Stocksnap, en WebP, dans
Ecoles/images_domaines). Pose aussi la couverture des écoles qui ont une photo de campus de leur site officiel.
Une image choisie dans l'admin n'est jamais remplacée."""
import unicodedata
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from Ecoles.models import Ecole, Filiere

DOSSIER = Path(__file__).resolve().parents[2] / 'images_domaines'

# Du plus précis au plus général : le premier mot trouvé l'emporte.
DOMAINES = [
    ('ia', ['intelligence artificielle']),
    ('donnees', ['donnees', 'data']),
    ('reseaux', ['cyber', 'securite', 'reseau', 'telecom']),
    ('informatique', ['informatique', 'logiciel', 'developpement', 'web', 'application', 'technologie']),
    ('energie', ['electro', 'energie', 'electrique', 'mecatronique', 'industriel']),
    ('droit', ['droit', 'juridique']),
    ('medias', ['media', 'communication', 'journalisme']),
    ('sante', ['sante', 'medecine']),
    ('agronomie', ['agronom', 'agricul']),
    ('lettres', ['lettres', 'langues', 'arts']),
    ('education', ['education', 'enseignement']),
    ('economie', ['economi']),
    ('gestion', ['gestion', 'comptab', 'audit', 'finance', 'banque']),
    ('management', ['management', 'projet', 'commerce', 'marketing']),
]

CAMPUS = {'universite-de-lome': 'campus-universite-de-lome.webp'}


def _simple(t):
    return ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c) != 'Mn')


def domaine(nom):
    t = _simple(nom)
    for code, mots in DOMAINES:
        if any(m in t for m in mots):
            return code
    return 'defaut'


class Command(BaseCommand):
    help = "Photos des filières (selon le domaine) et couvertures de campus."

    def handle(self, *a, **o):
        n = 0
        for f in Filiere.objects.filter(image=''):
            code = domaine(f.nom)
            f.image.save(f'{code}-{f.pk}.webp', ContentFile((DOSSIER / f'{code}.webp').read_bytes()), save=True)
            n += 1
        c = 0
        for slug, fichier in CAMPUS.items():
            e = Ecole.objects.filter(slug=slug, couverture='').first()
            if e:
                e.couverture.save(fichier, ContentFile((DOSSIER / fichier).read_bytes()), save=True)
                c += 1
        self.stdout.write(f"{n} filière(s) illustrée(s), {c} couverture(s) de campus")
