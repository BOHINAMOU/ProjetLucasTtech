"""Zone couverte de départ : Grand Lomé (centre Lomé, rayon 25 km), à affiner dans l'admin."""
from decimal import Decimal

from django.db import migrations


ANCIEN_ARRIVEE = ("Votre coursier {prenom_coursier} est arrivé ({vehicule}, {plaque}). "
                  "Donnez-lui le code de départ {code}.")
NOUVEAU_ARRIVEE = "Votre coursier {prenom_coursier} est arrivé ({vehicule}, {plaque})."


def creer(apps, schema_editor):
    apps.get_model('courses', 'Parametres').objects.filter(modele_message_arrivee=ANCIEN_ARRIVEE).update(
        modele_message_arrivee=NOUVEAU_ARRIVEE)
    Zone = apps.get_model('courses', 'Zone')
    if not Zone.objects.exists():
        Zone.objects.create(nom='Grand Lomé', centre_lat=6.137, centre_lng=1.212, rayon_km=Decimal('25'), active=True)


class Migration(migrations.Migration):
    dependencies = [('courses', '0005_prix_reel_zones')]
    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
