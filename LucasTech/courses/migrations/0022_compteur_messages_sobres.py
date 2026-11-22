from django.db import migrations

from courses.models import (MENTION_PRIX, MENTION_PRIX_V1, MESSAGE_ACCEPTATION, MESSAGE_ACCEPTATION_ANCIEN,
                            MESSAGE_ACCEPTATION_V2, MESSAGE_ARRIVEE, MESSAGE_ARRIVEE_ANCIEN, MESSAGE_ARRIVEE_V2,
                            MESSAGE_FIN, MESSAGE_FIN_V1)


def sobre(apps, schema_editor):
    P = apps.get_model('courses', 'Parametres')
    P.objects.filter(modele_message_acceptation__in=[MESSAGE_ACCEPTATION_ANCIEN, MESSAGE_ACCEPTATION_V2]).update(
        modele_message_acceptation=MESSAGE_ACCEPTATION)
    P.objects.filter(modele_message_arrivee__in=[MESSAGE_ARRIVEE_ANCIEN, MESSAGE_ARRIVEE_V2]).update(
        modele_message_arrivee=MESSAGE_ARRIVEE)
    P.objects.filter(modele_message_fin=MESSAGE_FIN_V1).update(modele_message_fin=MESSAGE_FIN)
    P.objects.filter(mention_prix=MENTION_PRIX_V1).update(mention_prix=MENTION_PRIX)
    # tarif de base de la moto : 200 FCFA (si encore à la valeur de départ)
    apps.get_model('courses', 'Categorie').objects.filter(code='moto', minimum=300).update(minimum=200)


class Migration(migrations.Migration):
    dependencies = [('courses', '0021_frais_annulation_200')]
    operations = [migrations.RunPython(sobre, migrations.RunPython.noop)]
