from django.db import migrations

from courses.models import MESSAGE_ACCEPTATION, MESSAGE_ACCEPTATION_V3, MESSAGE_ARRIVEE, MESSAGE_ARRIVEE_V3


def nom_complet(apps, schema_editor):
    P = apps.get_model('courses', 'Parametres')
    P.objects.filter(modele_message_acceptation=MESSAGE_ACCEPTATION_V3).update(modele_message_acceptation=MESSAGE_ACCEPTATION)
    P.objects.filter(modele_message_arrivee=MESSAGE_ARRIVEE_V3).update(modele_message_arrivee=MESSAGE_ARRIVEE)


class Migration(migrations.Migration):
    dependencies = [('courses', '0025_sans_prix_minute')]
    operations = [migrations.RunPython(nom_complet, migrations.RunPython.noop)]
