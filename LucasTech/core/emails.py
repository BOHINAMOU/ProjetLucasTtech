"""E-mails du site : tous les messages (texte brut) reçoivent automatiquement une version HTML soignée.

Le backend `JoliBackend` enveloppe chaque e-mail texte dans le gabarit `emails/joli.html` :
bandeau photo + logo, titre (= sujet), paragraphes, code à 6 chiffres en grand dans un encadré,
premier lien transformé en bouton vert, pied de page sobre. La version texte brut est conservée.
"""
import html
import re

from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend as _Smtp
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

SITE = 'https://lantantetechnologie.com'
URL = re.compile(r'(https?://[^\s<>"]+|(?<![\w/])/[a-z0-9][\w\-/]*/(?:\?[^\s<>"]*)?)', re.I)
SIGNATURE = re.compile(r"^\s*(—\s*)?(l['’]équipe lantante.*|lantante technologie\.?)\s*$", re.I)


def _lien(u):
    return u if u.startswith('http') else SITE + u


def _texte_html(t):
    """Échappe et rend les liens cliquables."""
    out, pos = [], 0
    for m in URL.finditer(t):
        out.append(html.escape(t[pos:m.start()]))
        u = m.group(0).rstrip('.,;)')
        out.append(f'<a href="{html.escape(_lien(u))}" style="color:#0B7A4B;font-weight:600;text-decoration:underline">'
                   f'{html.escape(u)}</a>')
        out.append(html.escape(m.group(0)[len(u):]))
        pos = m.end()
    out.append(html.escape(t[pos:]))
    return ''.join(out)


def analyser(sujet, corps):
    """Découpe le texte en blocs : ('p', html) | ('code', '123456') | ('bouton', (label, url))."""
    lignes = [l for l in corps.replace('\r', '').split('\n') if not SIGNATURE.match(l)]
    blocs_txt, cur = [], []
    for l in lignes:
        if l.strip():
            cur.append(l.strip())
        elif cur:
            blocs_txt.append(cur); cur = []
    if cur:
        blocs_txt.append(cur)

    veut_code = 'code' in (sujet + corps).lower()
    code_pris = bouton_pris = False
    blocs = []
    for bl in blocs_txt:
        texte = []
        for i, l in enumerate(bl):
            # code à 6 chiffres
            if veut_code and not code_pris:
                m = re.search(r'\b(\d{6})\b', l)
                if m and not re.search(r'\d{6}\d|\d\s\d{3}', l):
                    reste = (l[:m.start()] + l[m.end():]).strip().rstrip(':').strip()
                    if reste:
                        texte.append(reste + ' :' if l[:m.start()].strip().endswith(':') else reste)
                    if texte:
                        blocs.append(('p', '<br>'.join(_texte_html(x) for x in texte)))
                    texte = []
                    blocs.append(('code', m.group(1)))
                    code_pris = True
                    continue
            # premier lien seul sur sa ligne (ou « Libellé : lien ») → bouton
            m = re.fullmatch(r'(?:(.{1,45}?)\s*:\s*)?(https?://\S+|/[\w\-/]+/?(?:\?\S*)?)', l)
            if m and not bouton_pris:
                label = (m.group(1) or '').strip()
                if not label and texte and texte[-1].endswith(':') and len(texte[-1]) <= 46:
                    label = texte.pop()[:-1].strip()
                label = label or 'Ouvrir'
                if texte:
                    blocs.append(('p', '<br>'.join(_texte_html(x) for x in texte)))
                    texte = []
                blocs.append(('bouton', (label[:1].upper() + label[1:], _lien(m.group(2)))))
                bouton_pris = True
                continue
            texte.append(l)
        if texte:
            blocs.append(('p', '<br>'.join(_texte_html(x) for x in texte)))
    return blocs


def titre_de(sujet):
    t = re.sub(r'\s*[—\-–|]\s*Lantante Technologie\s*$', '', sujet or '').strip()
    t = re.sub(r'^\[[^\]]+\]\s*', '', t)
    return t or 'Lantante Technologie'


def html_de(sujet, corps):
    blocs = [(k, mark_safe(v) if k == 'p' else v) for k, v in analyser(sujet, corps)]
    return render_to_string('emails/joli.html', {'titre': titre_de(sujet), 'blocs': blocs, 'site': SITE})


def embellir(msg):
    """Renvoie le message avec une version HTML (si c'est un e-mail texte sans HTML)."""
    if getattr(msg, 'content_subtype', 'plain') != 'plain' or getattr(msg, 'alternatives', None):
        return msg
    try:
        h = html_de(msg.subject or '', msg.body or '')
    except Exception:  # jamais bloquer l'envoi à cause de la mise en forme
        return msg
    m = EmailMultiAlternatives(msg.subject, msg.body, msg.from_email, msg.to, bcc=msg.bcc, connection=msg.connection,
                               attachments=msg.attachments, headers=msg.extra_headers, cc=msg.cc, reply_to=msg.reply_to)
    m.attach_alternative(h, 'text/html')
    return m


class JoliBackend(_Smtp):
    def send_messages(self, email_messages):
        return super().send_messages([embellir(m) for m in email_messages])
