"""Tuiles de l'accueil de départ = celles de l'appli 1.8.5."""
from django.db import migrations

TUILES = [
    ('Commander une course', 'course', 'vert_fonce', 'course'),
    ('Concours', 'concours', 'vert', 'concours'),
    ("Recherche d'emploi", 'emploi', 'brun', 'emplois'),
    ('Boutique', 'boutique', 'orange', 'boutique'),
    ('Écoles', 'ecole', 'violet', 'ecoles'),
    ('Actualités', 'actualite', 'cyan', 'actualites'),
    ('Solde', 'solde', 'rose', 'solde'),
    ('Services', 'services', 'gris', 'services'),
]


def creer(apps, schema_editor):
    T = apps.get_model('api_mobile', 'TuileAccueil')
    if not T.objects.exists():
        for i, (libelle, icone, couleur, dest) in enumerate(TUILES, start=1):
            T.objects.create(libelle=libelle, icone=icone, couleur=couleur, destination=dest, ordre=i * 10)


class Migration(migrations.Migration):
    dependencies = [('api_mobile', '0005_tuiles_accueil')]
    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
