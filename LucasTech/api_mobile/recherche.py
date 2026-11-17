"""Recherche commune de l'appli : sans majuscules ni accents, sigles (« UL » → Université de Lomé), alias saisis
dans l'admin, petites fautes de frappe. Tri : sigle ou alias exact, début du nom, mot du nom, contient, proche.

Les catalogues font quelques centaines de lignes : le calcul se fait en Python (identique sur PostgreSQL et SQLite)."""
from difflib import SequenceMatcher

from django.db.models import Case, IntegerField, Value, When

from concours.search import normalize

STOP = {'de', 'des', 'du', 'la', 'le', 'les', 'l', 'd', 'et', 'en', 'a', 'au', 'aux', 'pour', 'of', 'the', 'and'}


def sigle(texte):
    """Initiales des mots qui comptent : « Université de Lomé » → « ul »."""
    mots = [m for m in normalize(texte).split() if m not in STOP]
    return ''.join(m[0] for m in mots) if len(mots) > 1 else ''


def _mots(q):
    mots = normalize(q).split()
    utiles = [m for m in mots if m not in STOP]
    return utiles or mots


def _proche(mot, jetons):
    return any(SequenceMatcher(None, mot, j).ratio() >= 0.8 for j in jetons if abs(len(j) - len(mot)) <= 3)


def score(q, nom, alias='', autres=''):
    """0 = ne correspond pas ; plus c'est grand, plus c'est pertinent."""
    nq = normalize(q)
    if not nq:
        return 1
    n = normalize(nom)
    aliases = [normalize(a) for a in (alias or '').split(',') if a.strip()]
    sigles = {s for s in [sigle(nom), *[sigle(a) for a in aliases]] if s}
    colle = nq.replace(' ', '')
    if colle in sigles or nq in aliases or nq == n:
        return 100
    if n.startswith(nq) or any(a.startswith(nq) for a in aliases):
        return 90
    if len(colle) >= 2 and any(s.startswith(colle) for s in sigles):
        return 85
    mots = _mots(q)
    titre = f" {n} {' '.join(aliases)} "
    if all(f' {m}' in titre for m in mots):
        return 75
    tout = f"{titre}{normalize(autres)[:3000]} "
    # un mot de 3 lettres ou plus peut être au milieu d'un mot ; plus court, seulement au début
    if all((m in tout) if len(m) >= 3 else (f' {m}' in tout) for m in mots):
        return 60
    jetons = titre.split()
    longs = [m for m in mots if len(m) >= 4]
    if longs and all(_proche(m, jetons) for m in longs):
        return 40
    return 0


def classer(objets, q, champs):
    """Objets qui correspondent, du plus pertinent au moins pertinent. champs(o) -> (nom, alias, autres)."""
    notes = [(score(q, *champs(o)), i, o) for i, o in enumerate(objets)]
    return [o for s, i, o in sorted((x for x in notes if x[0] > 0), key=lambda x: (-x[0], x[1]))]


def filtrer(qs, q, nom, *autres, alias=None):
    """Version queryset : garde l'ordre de pertinence et reste un queryset (filtres et pagination ensuite)."""
    q = (q or '').strip()
    if not q:
        return qs
    champs = [nom, *([alias] if alias else []), *autres]
    lignes = list(qs.values_list('pk', *champs).distinct())
    vus, ids = set(), []
    for ligne in classer(lignes, q, lambda r: (r[1] or '', (r[2] or '') if alias else '',
                                                ' '.join(str(x or '') for x in r[(3 if alias else 2):]))):
        if ligne[0] not in vus:
            vus.add(ligne[0])
            ids.append(ligne[0])
    if not ids:
        return qs.none()
    ordre = Case(*[When(pk=pk, then=Value(i)) for i, pk in enumerate(ids)], output_field=IntegerField())
    return qs.filter(pk__in=ids).annotate(_pertinence=ordre).order_by('_pertinence')
