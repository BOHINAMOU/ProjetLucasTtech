# -*- coding: utf-8 -*-
from Emploi.models import JobOffer, Skill

offer, created = JobOffer.objects.get_or_create(
    title="Professeur(e) de Physique-Chimie — Complexe Scolaire SANTIBON",
    defaults=dict(
        employer=None,
        domain='education',
        contract='cdi',
        city='Barkoissi',
        description=(
            "Le Complexe Scolaire SANTIBON, sis à Barkoissi, dans le cadre du renforcement de son "
            "personnel enseignant, recherche un(e) professeur(e) de Physique-Chimie pour la rentrée "
            "scolaire 2026-2027.\n\n"
            "Pour postuler : créez votre profil candidat sur Lantante Technologie et cliquez sur "
            "« Envoyer ma candidature », ou contactez directement le +228 98 53 51 65 (WhatsApp)."
        ),
        requirements="Enseignant(e) de Physique-Chimie, disponible pour la rentrée 2026-2027.",
        status='published',
        is_featured=True,
    ),
)
for name in ('Physique-Chimie', 'Enseignement'):
    skill = Skill.objects.filter(name__iexact=name).first() or Skill.objects.create(name=name)
    offer.skills.add(skill)
print('Créée' if created else 'Existante', '-', offer.title, '-', offer.get_absolute_url())
