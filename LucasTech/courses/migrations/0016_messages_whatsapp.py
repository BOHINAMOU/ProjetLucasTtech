from django.db import migrations

from courses.models import MESSAGE_ACCEPTATION, MESSAGE_ACCEPTATION_ANCIEN, MESSAGE_ARRIVEE, MESSAGE_ARRIVEE_ANCIEN


def nouveaux_messages(apps, schema_editor):
    P = apps.get_model('courses', 'Parametres')
    P.objects.filter(modele_message_acceptation=MESSAGE_ACCEPTATION_ANCIEN).update(modele_message_acceptation=MESSAGE_ACCEPTATION)
    P.objects.filter(modele_message_arrivee=MESSAGE_ARRIVEE_ANCIEN).update(modele_message_arrivee=MESSAGE_ARRIVEE)


class Migration(migrations.Migration):
    dependencies = [('courses', '0015_arrivee_pourboire')]
    operations = [migrations.RunPython(nouveaux_messages, migrations.RunPython.noop)]
