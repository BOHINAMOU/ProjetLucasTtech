from django.db import migrations

RENAMES = {"Publication d'une actualité": "Actualité", "Publication d'une offre d'emploi": "Offre d'emploi"}


def rename(apps, schema_editor):
    ServicePlan = apps.get_model('Emploi', 'ServicePlan')
    for old, new in RENAMES.items():
        ServicePlan.objects.filter(name=old).update(name=new)


class Migration(migrations.Migration):
    dependencies = [('Emploi', '0019_unique_publication_price')]
    operations = [migrations.RunPython(rename, migrations.RunPython.noop)]
