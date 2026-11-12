"""Crée 3 concours de DÉMONSTRATION, non publiés (visibles seulement par les admins), avec des
documents factices clairement marqués « démonstration » : aucune vraie épreuve n'est inventée.

    python manage.py concours_demo            # crée (idempotent)
    python manage.py concours_demo --publier  # les rend visibles au public
    python manage.py concours_demo --supprimer
"""
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from fpdf import FPDF

from concours.models import Contest, ContestCategory, ContestSession, Correction, ExamPaper

DEMO = [
    ('DEMO-ENS', "École normale supérieure (démonstration)", 'enseignement'),
    ('DEMO-SANTE', "Concours des écoles de santé (démonstration)", 'sante'),
    ('DEMO-ADMIN', "Concours de la fonction publique (démonstration)", 'administration'),
]
YEAR = 2025


def _pdf(title, lines):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 18)
    pdf.multi_cell(0, 10, title)
    pdf.ln(4)
    pdf.set_font('Helvetica', '', 12)
    for line in lines:
        pdf.multi_cell(0, 8, line)
    pdf.ln(6)
    pdf.set_text_color(200, 0, 0)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.multi_cell(0, 9, "DOCUMENT DE DEMONSTRATION - ce n'est pas une vraie epreuve.")
    return bytes(pdf.output())


class Command(BaseCommand):
    help = "Concours de démonstration (non publiés) pour tester les pages."

    def add_arguments(self, parser):
        parser.add_argument('--publier', action='store_true')
        parser.add_argument('--supprimer', action='store_true')

    def handle(self, *args, **opts):
        acronyms = [a for a, _n, _c in DEMO]
        if opts['supprimer']:
            for c in Contest.objects.filter(acronym__in=acronyms):
                for p in ExamPaper.objects.filter(session__contest=c):
                    for corr in p.corrections.all():
                        corr.file.delete(save=False)
                    p.file.delete(save=False)
                c.delete()
            self.stdout.write("Concours de démonstration supprimés.")
            return
        for acronym, name, cat_slug in DEMO:
            cat = ContestCategory.objects.get(slug=cat_slug)
            contest, _ = Contest.objects.get_or_create(acronym=acronym, defaults={
                'name': name, 'category': cat, 'country': 'Togo',
                'description': "Concours de démonstration pour vérifier l'affichage du site. "
                               "Les documents sont factices."})
            if opts['publier'] and not contest.is_published:
                contest.is_published = True
                contest.save(update_fields=['is_published'])
            session, _ = ContestSession.objects.get_or_create(contest=contest, year=YEAR)
            ContestSession.objects.get_or_create(contest=contest, year=YEAR - 1)
            if session.papers.exists():
                continue
            free = ExamPaper(session=session, title="Culture générale (démo)", subject="Culture générale",
                             duration="2 h", coefficient=2, is_free=True, order=1)
            free.file.save(f'{acronym.lower()}-demo-gratuit.pdf', ContentFile(_pdf(
                f"{acronym} {YEAR} - Culture generale (demo)", ["Sujet gratuit de demonstration."])), save=True)
            paid = ExamPaper(session=session, title="Épreuve de spécialité (démo)", subject="Spécialité",
                             duration="3 h", coefficient=3, is_free=False, order=2)
            paid.file.save(f'{acronym.lower()}-demo-payant.pdf', ContentFile(_pdf(
                f"{acronym} {YEAR} - Specialite (demo)", ["Sujet payant de demonstration."])), save=True)
            corr = Correction(paper=paid, kind='enseignant', author="Équipe Lantante (démo)")
            corr.file.save(f'{acronym.lower()}-demo-corrige.pdf', ContentFile(_pdf(
                f"{acronym} {YEAR} - Corrige (demo)", ["Corrige de demonstration."])), save=True)
        state = "publiés" if opts['publier'] else "non publiés (visibles par les admins seulement)"
        self.stdout.write(f"Concours de démonstration prêts, {state}.")
