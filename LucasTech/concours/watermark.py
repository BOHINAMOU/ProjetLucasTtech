"""PDF téléchargeable d'une épreuve ou d'un corrigé, avec filigrane incrusté (nom + e-mail de l'abonné
et « Lantante Technologie », en diagonale, léger, sur chaque page) pour décourager le partage.
Les images (JPG/PNG/WebP) sont converties en PDF. Utilisé par le site et par l'API mobile."""
import io
import unicodedata

from django.utils import timezone
from django.utils.text import slugify


class WatermarkUnavailable(Exception):
    pass


def _fitz():
    try:
        import pymupdf as fitz  # PyMuPDF
    except ImportError:
        try:
            import fitz  # anciennes versions de PyMuPDF
        except ImportError as exc:  # pragma: no cover - dépend de l'installation du serveur
            raise WatermarkUnavailable("PyMuPDF n'est pas installé") from exc
    return fitz


def _ascii(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()


def download_name(paper, kind):
    """Nom de fichier clair, ex. « ENS-2020-Mathematiques-sujet.pdf »."""
    contest = paper.session.contest
    sigle = getattr(contest, 'short_acronym', '') or contest.acronym
    sigle = ''.join(c for c in _ascii(sigle) if c.isalnum()).upper() or 'Concours'
    matiere = ''.join(w.capitalize() for w in slugify(_ascii(paper.subject or paper.title)).split('-')) or 'Epreuve'
    return f"{sigle}-{paper.session.year}-{matiere}-{'corrige' if kind == 'corrige' else 'sujet'}.pdf"


def watermarked_pdf(doc, user):
    """Octets du PDF filigrané. Lève WatermarkUnavailable si la bibliothèque manque."""
    fitz = _fitz()
    with doc.file.open('rb') as fh:
        raw = fh.read()
    name = doc.file.name.lower()
    if name.endswith('.pdf'):
        pdf = fitz.open(stream=raw, filetype='pdf')
    else:  # image -> PDF d'une page
        img = fitz.open(stream=raw, filetype=name.rsplit('.', 1)[-1])
        pdf = fitz.open('pdf', img.convert_to_pdf())
    who = (user.get_full_name() or '').strip()
    mark = f"{who + ' · ' if who else ''}{user.email} — Lantante Technologie"
    stamp = f"Téléchargé par {user.email} le {timezone.localtime().strftime('%d/%m/%Y %H:%M')} — lantantetechnologie.com"
    for page in pdf:
        r = page.rect
        size = max(10, min(r.width, r.height) / 26)
        for frac in (0.25, 0.55, 0.85):
            pivot = fitz.Point(r.width * 0.08, r.height * frac)
            page.insert_text(pivot, mark, fontsize=size, fontname='helv', color=(0.55, 0.55, 0.55),
                             fill_opacity=0.22, stroke_opacity=0.22, overlay=True,
                             morph=(pivot, fitz.Matrix(-30)))
        page.insert_text(fitz.Point(18, r.height - 10), stamp, fontsize=7, fontname='helv',
                         color=(0.4, 0.4, 0.4), fill_opacity=0.6, overlay=True)
    pdf.set_metadata({**(pdf.metadata or {}), 'producer': 'Lantante Technologie',
                      'subject': f'Document personnel de {user.email}'})
    out = io.BytesIO()
    pdf.save(out, garbage=3, deflate=True)
    return out.getvalue()
