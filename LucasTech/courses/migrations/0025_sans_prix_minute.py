from django.db import migrations


def sans_minute(apps, schema_editor):
    """Le prix ne compte plus les minutes de trajet : prise en charge + km, au moins le tarif de base.
    (L'attente au départ reste facturée à part.)"""
    apps.get_model('courses', 'Categorie').objects.update(prix_min=0)


class Migration(migrations.Migration):
    dependencies = [('courses', '0024_messagerie_support')]
    operations = [migrations.RunPython(sans_minute, migrations.RunPython.noop)]
