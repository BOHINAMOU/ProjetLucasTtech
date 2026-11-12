"""Concours de DÉMONSTRATION pour présenter la rubrique (web et future application).

- 6 concours fictifs « DEMO-… » dans 5 catégories, avec de vraies photos libres de droits
  (Wikimedia Commons, usage commercial autorisé : voir concours/demo_photos/CREDITS.json) ;
- plusieurs années, des épreuves et des corrigés FACTICES, clairement marqués « Démonstration » ;
- badge « Démo » visible partout ; ces concours ne peuvent pas être choisis dans un abonnement.

    python manage.py concours_demo              # crée / met à jour (non publiés)
    python manage.py concours_demo --publier    # crée / met à jour et publie
    python manage.py concours_demo --retirer    # dépublie (garde les données)
    python manage.py concours_demo --supprimer  # supprime tout (concours, fichiers, photos)
"""
import json
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db.models import Q
from fpdf import FPDF

from concours.models import Contest, ContestCategory, ContestSession, Correction, ExamPaper

PHOTOS = Path(__file__).resolve().parents[2] / 'demo_photos'

DEMO = [
    # sigle, nom, catégorie, préfixe photo, description, années -> épreuves
    ('DEMO-ENS', "École normale supérieure — exemple", 'enseignement', 'ens',
     "Concours de recrutement des élèves-professeurs (exemple de démonstration).",
     {2025: ['culture', 'maths', 'francais'], 2024: ['maths', 'francais'], 2023: ['culture'], 2020: []}),
    ('DEMO-INFO', "Concours d'informatique — exemple", 'informatique', 'info',
     "Entrée en école d'informatique et de réseaux (exemple de démonstration).",
     {2025: ['logique', 'maths', 'anglais'], 2024: ['logique', 'maths']}),
    ('DEMO-SANTE', "Écoles de santé : infirmiers et sages-femmes — exemple", 'sante', 'sante',
     "Concours d'entrée dans les écoles paramédicales (exemple de démonstration).",
     {2025: ['culture', 'biologie', 'francais'], 2024: ['biologie'], 2023: ['culture', 'biologie']}),
    ('DEMO-DOUANES', "Concours des douanes — exemple", 'administration', 'douanes',
     "Recrutement d'agents et de contrôleurs des douanes (exemple de démonstration).",
     {2025: ['culture', 'droit', 'maths'], 2024: ['culture', 'droit']}),
    ('DEMO-FP', "Fonction publique — exemple", 'administration', 'fp',
     "Concours administratifs de la fonction publique (exemple de démonstration).",
     {2025: ['culture', 'redaction'], 2024: ['culture', 'redaction'], 2023: ['redaction']}),
    ('DEMO-GEND', "Gendarmerie nationale — exemple", 'securite', 'gend',
     "Recrutement des élèves gendarmes (exemple de démonstration).",
     {2025: ['culture', 'francais', 'maths'], 2024: ['culture']}),
]
SUBJECTS = {  # clé -> (titre, matière, durée, coefficient)
    'culture': ("Culture générale", "Culture générale", "2 h", 2),
    'maths': ("Mathématiques", "Mathématiques", "3 h", 3),
    'francais': ("Français : dissertation", "Français", "3 h", 3),
    'logique': ("Logique et algorithmique", "Informatique", "2 h", 3),
    'anglais': ("Anglais", "Anglais", "1 h 30", 1),
    'biologie': ("Sciences biologiques", "Biologie", "2 h", 3),
    'droit': ("Droit et économie", "Droit", "3 h", 2),
    'redaction': ("Note de synthèse", "Rédaction administrative", "4 h", 4),
}


def _pdf(title, subtitle, body):
    pdf = FPDF()
    pdf.set_auto_page_break(True, 20)
    pdf.add_page()
    pdf.set_fill_color(15, 122, 69)
    pdf.rect(0, 0, 210, 30, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_xy(12, 9)
    pdf.cell(0, 8, title)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_xy(12, 18)
    pdf.cell(0, 6, subtitle)
    pdf.set_text_color(200, 0, 0)
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_xy(12, 40)
    pdf.multi_cell(186, 7, "DOCUMENT DE DEMONSTRATION - ce n'est pas une vraie epreuve officielle.")
    pdf.set_text_color(30, 30, 30)
    pdf.set_font('Helvetica', '', 11)
    pdf.ln(4)
    for line in body:
        pdf.set_x(12)
        pdf.multi_cell(186, 7, line)
        pdf.ln(2)
    return bytes(pdf.output())


def _ascii(s):
    import unicodedata
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()


class Command(BaseCommand):
    help = "Concours de démonstration avec photos (voir l'aide du fichier)."

    def add_arguments(self, parser):
        parser.add_argument('--publier', action='store_true')
        parser.add_argument('--retirer', action='store_true')
        parser.add_argument('--supprimer', action='store_true')

    def _demo_qs(self):
        return Contest.objects.filter(Q(is_demo=True) | Q(acronym__startswith='DEMO-'))

    def _delete(self, contests):
        for c in contests:
            for p in ExamPaper.objects.filter(session__contest=c):
                for corr in p.corrections.all():
                    corr.file.delete(save=False)
                p.file.delete(save=False)
            for f in (c.logo, c.cover):
                if f:
                    f.delete(save=False)
            c.delete()

    def handle(self, *args, **opts):
        if opts['supprimer']:
            n = self._demo_qs().count()
            self._delete(self._demo_qs())
            self.stdout.write(f"{n} concours de démonstration supprimés.")
            return
        if opts['retirer']:
            n = self._demo_qs().update(is_published=False)
            self.stdout.write(f"{n} concours de démonstration retirés du site.")
            return

        credits = json.loads((PHOTOS / 'CREDITS.json').read_text(encoding='utf-8'))
        keep = [d[0] for d in DEMO]
        self._delete(self._demo_qs().exclude(acronym__in=keep))  # anciens exemples
        for acronym, name, cat_slug, photo, desc, years in DEMO:
            cat = ContestCategory.objects.get(slug=cat_slug)
            c, _ = Contest.objects.get_or_create(acronym=acronym, defaults={'name': name, 'category': cat})
            c.name, c.category, c.description, c.is_demo, c.country = name, cat, desc, True, 'Togo'
            cr = [credits[f'{photo}-cover'], credits[f'{photo}-profil']]
            c.photo_credit = " · ".join(f"{x['auteur'] or 'Auteur inconnu'} ({x['licence']})" for x in cr)
            c.photo_credit_url = cr[0]['source']
            if opts['publier']:
                c.is_published = True
            for field, suffix in (('cover', 'cover'), ('logo', 'profil')):
                f = getattr(c, field)
                if f:
                    f.delete(save=False)
                f.save(f'{acronym.lower()}-{suffix}.jpg',
                       ContentFile((PHOTOS / f'{photo}-{suffix}.jpg').read_bytes()), save=False)
            c.save()
            for p in ExamPaper.objects.filter(session__contest=c):  # documents de démo régénérés à chaque fois
                for corr in p.corrections.all():
                    corr.file.delete(save=False)
                p.file.delete(save=False)
            c.sessions.all().delete()
            for year, subjects in years.items():
                s = ContestSession.objects.create(contest=c, year=year)
                latest = year == max(years)
                for i, key in enumerate(subjects):
                    title, matiere, duree, coef = SUBJECTS[key]
                    p = ExamPaper(session=s, title=f"{title} (démo)", subject=matiere, duration=duree,
                                  coefficient=coef, order=i, is_free=latest and i == 0,
                                  description="Sujet factice pour la démonstration du site.")
                    head = _ascii(f"{acronym} {year} - {title}")
                    p.file.save(f'{acronym.lower()}-{year}-{key}.pdf', ContentFile(_pdf(
                        head, _ascii(f"Exemple de sujet - duree {duree} - coefficient {coef}"),
                        ["Exercice 1 : texte de demonstration.", "Exercice 2 : texte de demonstration.",
                         "Ce document sert uniquement a montrer le lecteur en ligne du site."])), save=True)
                    if i % 2 == 0:  # un sujet sur deux a un corrigé (les autres : « Corrigé non disponible »)
                        corr = Correction(paper=p, kind='officiel' if i == 0 else 'enseignant',
                                          author="Équipe Lantante (démo)")
                        corr.file.save(f'{acronym.lower()}-{year}-{key}-corrige.pdf', ContentFile(_pdf(
                            _ascii(f"Corrige - {head}"), "Exemple de corrige",
                            ["Correction de l'exercice 1 (demonstration).",
                             "Correction de l'exercice 2 (demonstration)."])), save=True)
        state = "publiés" if opts['publier'] else "créés (non publiés : lancez --publier pour les afficher)"
        self.stdout.write(f"{len(DEMO)} concours de démonstration {state}.")
