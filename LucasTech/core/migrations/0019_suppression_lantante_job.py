"""Suppression de l'ancien « Lantante Job » (application Emploi), confirmée par le propriétaire.

Sauvegarde faite avant : base complète + export des données + fichiers (~/backups/lantante-job-*).
Les fichiers (CV, pièces) restent sur le disque. Le module « Emplois » (Offres) n'est pas concerné.
"""
from django.db import migrations


def supprimer(apps, schema_editor):
    c = schema_editor.connection
    tables = [t for t in c.introspection.table_names() if t.startswith('Emploi_')]
    qn = schema_editor.quote_name
    cascade = ' CASCADE' if c.vendor == 'postgresql' else ''
    for t in tables:
        schema_editor.execute(f'DROP TABLE IF EXISTS {qn(t)}{cascade}')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    ContentType.objects.filter(app_label='Emploi').delete()  # permissions et historique admin liés
    schema_editor.execute("DELETE FROM django_migrations WHERE app = 'Emploi'")


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0018_exemption_2fa'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]
    operations = [migrations.RunPython(supprimer, migrations.RunPython.noop)]
