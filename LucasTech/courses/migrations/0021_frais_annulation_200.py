from django.db import migrations, models


def frais_200(apps, schema_editor):
    """Frais d'annulation : 200 FCFA par défaut (jamais le prix de la course). Valeurs modifiées dans l'admin : gardées."""
    P = apps.get_model('courses', 'Parametres')
    P.objects.filter(frais_annulation_voiture=500).update(frais_annulation_voiture=200)
    P.objects.filter(frais_absent_moto=300).update(frais_absent_moto=200)
    P.objects.filter(frais_absent_voiture=700).update(frais_absent_voiture=200)


class Migration(migrations.Migration):
    dependencies = [('courses', '0020_discussion_fermee_a_la_fin')]
    operations = [
        migrations.AlterField('parametres', 'frais_annulation_voiture',
                              models.PositiveIntegerField("Frais d'annulation voiture (FCFA)", default=200)),
        migrations.AlterField('parametres', 'frais_absent_moto',
                              models.PositiveIntegerField("Frais client absent moto (FCFA)", default=200)),
        migrations.AlterField('parametres', 'frais_absent_voiture',
                              models.PositiveIntegerField("Frais client absent voiture (FCFA)", default=200)),
        migrations.RunPython(frais_200, migrations.RunPython.noop),
    ]
