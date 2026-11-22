from django.db import migrations, models


def nouvelle_attente(apps, schema_editor):
    """Valeurs encore à l'ancien réglage par défaut : 2 min gratuites puis 100 F/min (moto), 200 F/min (voiture)."""
    P = apps.get_model('courses', 'Parametres')
    P.objects.filter(attente_gratuite_min=3).update(attente_gratuite_min=2)
    P.objects.filter(prix_attente_moto=25).update(prix_attente_moto=100)
    P.objects.filter(prix_attente_voiture=50).update(prix_attente_voiture=200)


class Migration(migrations.Migration):
    dependencies = [('courses', '0018_message_fin')]
    operations = [
        migrations.AlterField('parametres', 'attente_gratuite_min', models.PositiveSmallIntegerField(
            "Attente gratuite (min)", default=2,
            help_text="Après l'arrivée du coursier, le client a ces minutes gratuites ; ensuite l'attente est facturée.")),
        migrations.AlterField('parametres', 'prix_attente_moto',
                              models.PositiveIntegerField("Prix de l'attente moto (FCFA/min)", default=100)),
        migrations.AlterField('parametres', 'prix_attente_voiture',
                              models.PositiveIntegerField("Prix de l'attente voiture (FCFA/min)", default=200)),
        migrations.RunPython(nouvelle_attente, migrations.RunPython.noop),
    ]
