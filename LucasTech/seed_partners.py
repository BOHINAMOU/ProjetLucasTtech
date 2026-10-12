# -*- coding: utf-8 -*-
from django.core.files import File
from core.models import Partner

PLAN = [
    dict(
        name="Lantante Technologie",
        logo_file="lantante_logo.png",
        country="Togo",
        domain="Technologie, formations & e-commerce",
        description=(
            "Plateforme togolaise de formations technologiques, de services numériques "
            "et de boutique en ligne, engagée à accompagner la jeunesse africaine vers "
            "l'autonomisation numérique et l'entrepreneuriat."
        ),
        website="https://lantantetechnologie.com/",
        email="lucastech.tg@gmail.com",
        whatsapp="22891973334",
        order=1,
    ),
    dict(
        name="Premier FORUM-CHANTIER African WeYouthIMPACT 30/63",
        logo_file="forumchantier_logo.png",
        country="Côte d'Ivoire — Afrique",
        domain="Engagement jeunesse & développement durable en Afrique (Agendas 2030 & 2063)",
        description=(
            "Initiative panafricaine hybride associant un FORUM continental de haut niveau "
            "à un CHANTIER multi-pays de transformation sociale, économique et "
            "environnementale, arrimée aux Agendas 2030 des Nations Unies et 2063 de "
            "l'Union Africaine. Autour de 7 piliers — Feed Africa, Peacemakers, Mother "
            "Nature, Africa's Windows, Cultural Pathways, Tech and Power4All, Women & "
            "Youth Matter — elle mobilise chaque année plus de 5 000 femmes et jeunes "
            "à travers plusieurs pays africains."
        ),
        website="https://www.forumchantierweyouthimpact.org/",
        order=2,
    ),
]

total_created = 0
for p in PLAN:
    logo_file = p.pop('logo_file')
    obj, created = Partner.objects.get_or_create(
        name=p['name'],
        defaults={**p, 'is_active': True},
    )
    if created:
        total_created += 1
        with open(f'/tmp/partners_new/{logo_file}', 'rb') as f:
            obj.logo.save(logo_file, File(f), save=True)
    print(('Créé' if created else 'Existant'), '-', obj.name)

print('--- Total partenaires ---', Partner.objects.count(), '(', total_created, 'nouveaux )')
