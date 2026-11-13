"""Recherche des concours (site et application) : sans accents ni majuscules, mots partiels,
plusieurs mots dans n'importe quel ordre, dans le sigle, le nom, la catégorie, le pays et la description.
Tri par pertinence : sigle exact, puis sigle qui commence par…, puis nom, puis catégorie, puis description.

Le catalogue compte quelques dizaines de concours : la recherche se fait en Python, ce qui marche à
l'identique sur PostgreSQL (serveur) et SQLite (tests) sans extension « unaccent »."""
import re
import unicodedata

_WORD = re.compile(r"[a-z0-9]+")
# Mots trop courants pour filtrer quoi que ce soit.
_STOP = {'de', 'des', 'du', 'la', 'le', 'les', 'l', 'd', 'et', 'en', 'a', 'au', 'aux', 'pour', 'concours'}


def normalize(text):
    text = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode().lower()
    return ' '.join(_WORD.findall(text))


def _words(q):
    words = normalize(q).split()
    useful = [w for w in words if w not in _STOP]
    return useful or words


def score(contest, q):
    """0 = ne correspond pas ; plus le score est grand, plus le concours est pertinent."""
    words = _words(q)
    if not words:
        return 1
    sigle = normalize(contest.acronym)
    short = normalize(getattr(contest, 'short_acronym', '') or contest.acronym)
    name = normalize(contest.name)
    cat = normalize(contest.category.name if contest.category_id else '')
    country = normalize(contest.country)
    desc = normalize(contest.description)
    haystack = f' {sigle} {short} {name} {cat} {country} {desc} '
    # chaque mot doit apparaître quelque part (début de mot : « norm » trouve « normale »)
    if not all(f' {w}' in haystack for w in words):
        return 0
    phrase = ' '.join(words)
    s = 1
    if phrase in (sigle, short):
        s += 1000
    elif sigle.startswith(phrase) or short.startswith(phrase):
        s += 500
    if f' {phrase}' in f' {name}':
        s += 300
    s += 60 * sum(1 for w in words if f' {w}' in f' {name}')
    if phrase in cat or any(f' {w}' in f' {cat}' for w in words):
        s += 120
    return s


def search_contests(contests, q):
    """Filtre et trie une liste (ou un queryset) de concours selon la recherche [q]."""
    if not (q or '').strip():
        return list(contests)
    scored = [(score(c, q), c) for c in contests]
    return [c for s, c in sorted(scored, key=lambda t: (-t[0], t[1].acronym)) if s > 0]
