"""Reçu PDF d'un paiement réussi (à conserver : demandé à l'entrée d'un événement ou en cas de réclamation)."""
from django.conf import settings
from django.contrib.staticfiles import finders
from django.utils import timezone
from fpdf import FPDF

from core.models import SiteSettings

GREEN = (15, 122, 69)
INK = (17, 20, 18)
GREY = (95, 102, 98)
LIGHT = (238, 246, 241)

REPLACEMENTS = {"–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "•": "-", "…": "...",
                " ": " ", " ": " ", "×": "x"}


def txt(value):
    s = str(value or "")
    for a, b in REPLACEMENTS.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def money(n):
    return f"{int(n or 0):,}".replace(",", " ") + " FCFA"


def local(dt, fmt="%d/%m/%Y à %H:%M"):
    return timezone.localtime(dt).strftime(fmt) if dt else "-"


class Receipt(FPDF):
    def footer(self):
        self.set_y(-16)
        self.set_draw_color(*GREEN)
        self.set_line_width(0.5)
        self.line(15, self.get_y(), 195, self.get_y())
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        site = getattr(settings, "SITE_URL", "").split("://")[-1].rstrip("/") or "lantantetechnologie.com"
        self.cell(0, 8, txt(f"{site} - Reçu généré le {local(timezone.now())}"), align="C")


def build_receipt(p):
    site = SiteSettings.load()
    pdf = Receipt(format="A4")
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    logo = finders.find("images/logo.png")
    if logo:
        try:
            from PIL import Image
            with Image.open(logo) as im:
                im = im.convert("RGBA")
                im.thumbnail((200, 200))  # PDF léger
                pdf.image(im, x=15, y=12, h=18)
        except Exception:
            pass
    pdf.set_xy(38, 13)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*INK)
    pdf.cell(110, 8, txt("Reçu de paiement"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(38)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GREY)
    pdf.cell(110, 6, txt("Lantante Technologie - Lomé, Togo"))
    pdf.set_xy(158, 14)
    pdf.set_fill_color(*GREEN)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(37, 11, txt("PAYÉ"), align="C", fill=True)
    pdf.set_y(36)
    pdf.set_draw_color(*GREEN)
    pdf.set_line_width(0.8)
    pdf.line(15, 36, 195, 36)
    pdf.ln(5)

    def title(text):
        pdf.ln(2)
        pdf.set_fill_color(*LIGHT)
        pdf.set_text_color(*INK)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, txt("  " + text), fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    def row(label, value, bold=False):
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*GREY)
        pdf.cell(55, 7, txt(label))
        pdf.set_font("Helvetica", "B" if bold else "", 10)
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, 7, txt(value), new_x="LMARGIN", new_y="NEXT")

    title("Paiement")
    row("Référence", p.reference, bold=True)
    if p.fedapay_id:
        row("Transaction FedaPay", p.fedapay_id)
    row("Date", local(p.paid_at or p.created_at))
    row("Moyen de paiement", p.operator_label or "Mobile Money")
    row("Objet", p.description, bold=True)
    row("Montant payé", money(p.amount), bold=True)

    title("Client")
    row("Nom", p.full_name, bold=True)
    row("Téléphone", p.phone_display)
    digits = lambda v: "".join(c for c in (v or "") if c.isdigit())[-8:]
    if p.whatsapp and digits(p.whatsapp) != digits(p.phone):
        row("WhatsApp", p.whatsapp)
    if p.email:
        row("Email", p.email)
    if p.city:
        row("Localité", p.city)

    if p.kind == "ticket" and p.event:
        ev = p.event
        title("Événement")
        row("Événement", ev.title, bold=True)
        row("Date", local(ev.starts_at))
        row("Lieu", ev.location)
        title("Tickets")
        widths = (70, 40, 70)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(255, 255, 255)
        pdf.set_fill_color(*GREEN)
        for w, h in zip(widths, ("Type", "Code", "Au nom de")):
            pdf.cell(w, 8, txt(h), fill=True)
        pdf.ln()
        pdf.set_text_color(*INK)
        for i, t in enumerate(p.tickets.select_related("ticket_type")):
            pdf.set_fill_color(*(LIGHT if i % 2 else (255, 255, 255)))
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(widths[0], 8, txt(t.ticket_type.name), fill=True)
            pdf.set_font("Courier", "B", 11)
            pdf.cell(widths[1], 8, txt(t.code), fill=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(widths[2], 8, txt(t.holder_name), fill=True)
            pdf.ln()
        note = ("- Nous vous appelons pour la livraison de vos tickets.\n"
                "- Le jour de l'événement, présentez ce reçu (papier ou téléphone) ou donnez votre nom à l'entrée.\n"
                "- Chaque code n'est valable qu'une seule fois.")
    elif p.kind in ("product", "shop"):
        if p.items:
            title("Articles")
            for it in p.items:
                row(f"{it.get('name', 'Article')}", f"{it.get('quantity', 1)} x {money(it.get('price'))}")
        note = ("- Nous vous appelons pour convenir de la livraison.\n"
                "- Conservez ce reçu : il vous sera demandé en cas de réclamation.")
    else:
        note = ("- Conservez ce reçu : il vous sera demandé en cas de réclamation.\n"
                "- Notre équipe vous contacte pour la suite si nécessaire.")

    pdf.ln(5)
    pdf.set_fill_color(255, 247, 222)
    pdf.set_text_color(107, 76, 0)
    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(0, 6, txt("Important"), fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, txt(note), fill=True, new_x="LMARGIN", new_y="NEXT")

    contacts = " / ".join(x for x in (getattr(site, "whatsapp_1", ""), getattr(site, "whatsapp_2", "")) if x)
    if contacts:
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*GREY)
        pdf.multi_cell(0, 5, txt(f"Service client Lantante Technologie (WhatsApp) : {contacts}"), align="C")
    return bytes(pdf.output())
