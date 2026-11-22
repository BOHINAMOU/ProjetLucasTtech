from django.db import migrations, models


def fermer(apps, schema_editor):
    apps.get_model('courses', 'Parametres').objects.filter(chat_ouvert_apres_fin_min=60).update(chat_ouvert_apres_fin_min=0)


class Migration(migrations.Migration):
    dependencies = [('courses', '0019_attente_par_defaut')]
    operations = [
        migrations.AlterField('parametres', 'chat_ouvert_apres_fin_min', models.PositiveSmallIntegerField(
            "Discussion ouverte après la fin (min)", default=0,
            help_text="0 : la discussion s'arrête dès la fin de la course (l'historique reste visible).")),
        migrations.RunPython(fermer, migrations.RunPython.noop),
    ]
