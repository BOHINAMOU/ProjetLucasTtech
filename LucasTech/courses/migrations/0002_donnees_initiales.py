"""Données de départ de Lantante Express : services, catégories et tarifs (FCFA), plages horaires, paramètres."""
from datetime import time
from decimal import Decimal

from django.db import migrations

SERVICES = [('moto', 'Moto', 1), ('voiture', 'Voiture', 2), ('cargo', 'Cargo', 3)]
# service, code, nom, véhicule, active, capacité, poids max, ordre, prise en charge, km, min, minimum, commission
CATEGORIES = [
    ('moto', 'moto', 'Moto', 'moto', True, 1, None, 1, 150, 100, 10, 300, 15),
    ('voiture', 'voiture-non-climatisee', 'Non climatisée', 'voiture', True, 4, None, 1, 400, 200, 20, 800, 20),
    ('voiture', 'voiture-climatisee', 'Climatisée', 'voiture', True, 4, None, 2, 500, 250, 25, 1000, 20),
    ('voiture', 'prestige', 'Prestige', 'voiture', False, 4, None, 3, 1000, 400, 40, 2500, 20),
    ('cargo', 'cargo-petit-colis', 'Petit colis', 'moto', False, 0, 10, 1, 300, 120, 10, 500, 20),
    ('cargo', 'cargo-volumineux', 'Colis volumineux', 'voiture', False, 0, 50, 2, 800, 250, 20, 1500, 20),
]
PLAGES = [('Journée', time(6), time(20), Decimal('1.00')), ('Soirée', time(20), time(23), Decimal('1.10')),
          ('Nuit', time(23), time(6), Decimal('1.25'))]


def creer(apps, schema_editor):
    Service = apps.get_model('courses', 'Service')
    Categorie = apps.get_model('courses', 'Categorie')
    PlageHoraire = apps.get_model('courses', 'PlageHoraire')
    Parametres = apps.get_model('courses', 'Parametres')
    services = {}
    for code, nom, ordre in SERVICES:
        services[code], _ = Service.objects.get_or_create(code=code, defaults={'nom': nom, 'ordre': ordre})
    for s, code, nom, veh, active, cap, poids, ordre, pec, km, mn, mini, com in CATEGORIES:
        Categorie.objects.get_or_create(code=code, defaults=dict(
            service=services[s], nom=nom, vehicule=veh, active=active, capacite=cap, poids_max=poids, ordre=ordre,
            prise_en_charge=pec, prix_km=km, prix_min=mn, minimum=mini, commission_pct=Decimal(com)))
    if not PlageHoraire.objects.exists():
        for nom, debut, fin, coef in PLAGES:
            PlageHoraire.objects.create(nom=nom, debut=debut, fin=fin, coefficient=coef)
    Parametres.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [('courses', '0001_initial')]
    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
