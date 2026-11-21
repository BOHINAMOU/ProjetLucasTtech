"""Service Tricycle et Prestige activés (demande du 21/11/2026),
icônes des catégories existantes."""
from decimal import Decimal

from django.db import migrations

ICONES = {'moto': 'moto', 'voiture-non-climatisee': 'voiture', 'voiture-climatisee': 'voiture_clim',
          'prestige': 'prestige', 'cargo-petit-colis': 'colis', 'cargo-volumineux': 'camionnette'}
ORDRE = {'moto': 1, 'tricycle': 2, 'voiture': 3, 'cargo': 4}


def appliquer(apps, schema_editor):
    Service = apps.get_model('courses', 'Service')
    Categorie = apps.get_model('courses', 'Categorie')
    tricycle, _ = Service.objects.get_or_create(code='tricycle', defaults={'nom': 'Tricycle', 'ordre': 2})
    for code, ordre in ORDRE.items():
        Service.objects.filter(code=code).update(ordre=ordre)
    Categorie.objects.get_or_create(code='tricycle', defaults=dict(
        service=tricycle, nom='Tricycle', vehicule='moto', icone='tricycle', active=True, capacite=3, ordre=1,
        prise_en_charge=300, prix_km=150, prix_min=15, minimum=500, commission_pct=Decimal(15)))
    for code, icone in ICONES.items():
        Categorie.objects.filter(code=code, icone='').update(icone=icone)
    Categorie.objects.filter(code='prestige').update(active=True)


class Migration(migrations.Migration):
    dependencies = [('courses', '0010_icones_tricycle')]
    operations = [migrations.RunPython(appliquer, migrations.RunPython.noop)]
