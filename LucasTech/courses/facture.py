"""Facture PDF d'une course terminée (Lantante Express) : téléchargeable par le client depuis l'appli."""
from django.contrib.staticfiles import finders
from django.utils import timezone

from Payments.receipt import GREEN, GREY, INK, LIGHT, Receipt, local, money, txt


def _km(v):
    return f"{float(v or 0):.1f} km".replace('.', ',')


def build_facture(c):
    d = c.detail_prix or {}
    part = c.partenaire
    pdf = Receipt(format="A4")
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()

    # En-tête : logo, titre, numéro
    logo = finders.find("images/logo.png")
    if logo:
        try:
            from PIL import Image
            with Image.open(logo) as im:
                im = im.convert("RGBA")
                im.thumbnail((200, 200))
                pdf.image(im, x=15, y=12, h=16)
        except Exception:  # pragma: no cover - logo facultatif
            pass
    pdf.set_xy(15, 14)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*INK)
    pdf.cell(0, 9, txt("Facture"), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 5, txt(f"N° {c.numero_recu}  ·  Course {c.reference}"), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, txt(f"Le {local(c.terminee_le)}"), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # Bandeau du total
    pdf.set_fill_color(*GREEN)
    pdf.set_text_color(255, 255, 255)
    y = pdf.get_y()
    pdf.rect(15, y, 180, 24, style="F")
    pdf.set_xy(20, y + 4)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(80, 5, txt("Total payé"))
    pdf.set_xy(20, y + 10)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(80, 10, txt(money(c.total_client)))
    pdf.set_xy(110, y + 7)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(80, 5, txt(f"Paiement : {c.get_moyen_paiement_display()}\n{c.categorie.service.nom} - {c.categorie.nom}"),
                   align="R")
    pdf.set_y(y + 30)

    def titre(t):
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*INK)
        pdf.cell(0, 8, txt(t), new_x="LMARGIN", new_y="NEXT")

    def ligne(a, b, gras=False):
        pdf.set_font("Helvetica", "B" if gras else "", 11 if gras else 10)
        pdf.set_text_color(*(INK if gras else GREY))
        pdf.cell(120, 7, txt(a))
        pdf.set_text_color(*INK)
        pdf.cell(60, 7, txt(b), align="R", new_x="LMARGIN", new_y="NEXT")

    # Trajet
    titre("Trajet")
    ligne("Départ", (c.depart_adresse or "-")[:70])
    ligne("Arrivée", (c.arrivee_adresse or "-")[:70])
    # distance EXACTE parcourue (compteur), jamais l'estimation faite à la commande
    km = d['compteur_km'] if d.get('compteur_km') is not None else float(c.distance_reelle_km or 0)
    ligne("Distance parcourue", _km(km))
    if c.demarree_le and c.terminee_le:
        minutes = max(1, round((c.terminee_le - c.demarree_le).total_seconds() / 60))
        ligne("Durée", f"{minutes} min  ({local(c.demarree_le, '%H:%M')} - {local(c.terminee_le, '%H:%M')})")
    if part:
        vehicule = " ".join(x for x in (part.marque, part.modele, part.couleur) if x)
        ligne("Coursier", f"{part.user.first_name}  ·  {vehicule}  ·  {part.plaque}".strip(" ·"))
    pdf.ln(3)

    # Détail du prix
    titre("Détail du prix")
    pdf.set_fill_color(*LIGHT)
    cat = c.categorie
    if cat.prise_en_charge:
        ligne("Prise en charge", money(cat.prise_en_charge))
    if cat.prix_km:
        ligne(f"Distance : {_km(km)} x {money(cat.prix_km)}", money(round(float(km) * cat.prix_km)))
    coef = d.get('coefficient', 1) or 1
    if coef != 1:
        ligne(f"Horaire {d.get('plage', '')}", f"x {coef}")
    if c.prix_final is not None and c.prix_final == cat.minimum:
        ligne("Tarif de base appliqué (minimum)", money(cat.minimum))
    for s in d.get('supplements', []):
        ligne(s.get('motif', 'Supplément'), money(s.get('montant')))
    ligne("Prix de la course", money(c.prix_final if c.prix_final is not None else c.prix_estime), gras=True)
    if c.reduction:
        ligne("Réduction fidélité", "- " + money(c.reduction))
    if c.frais_impayes:
        ligne("Frais d'annulation précédents", money(c.frais_impayes))
    pdf.set_draw_color(*GREEN)
    pdf.line(15, pdf.get_y() + 1, 195, pdf.get_y() + 1)
    pdf.ln(3)
    ligne("Total payé", money(c.total_client), gras=True)
    if d.get('paye_solde') and d.get('paye_especes'):
        ligne("Payé avec le solde", money(d['paye_solde']))
        ligne("Payé en espèces", money(d['paye_especes']))
    if d.get('pourboire'):
        ligne("Pourboire au coursier (en plus)", money(d['pourboire']))
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(0, 5, txt("Merci de nous avoir choisis. Lantante Express - à très bientôt.\n"
                             f"Document généré le {local(timezone.now())}."), align="C")
    return bytes(pdf.output())
