from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Events', '0004_event_kind_min_amount')]

    operations = [
        migrations.AlterField(
            model_name='event', name='location',
            field=models.CharField(blank=True, help_text='Facultatif. Ex : Palais des Congrès, Lomé', max_length=200,
                                   verbose_name='Lieu'),
        ),
        migrations.AlterField(
            model_name='event', name='starts_at',
            field=models.DateTimeField(blank=True, help_text='Facultatif (ex. une collecte de soutien sans date).',
                                       null=True, verbose_name='Date et heure de début'),
        ),
    ]
