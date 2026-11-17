import secrets

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import Repetiteurs.models


def remplir(apps, schema_editor):
    Candidature = apps.get_model('Repetiteurs', 'Candidature')
    for c in Candidature.objects.filter(jeton=''):
        c.jeton = secrets.token_urlsafe(32)
        c.save(update_fields=['jeton'])


class Migration(migrations.Migration):

    dependencies = [
        ('Repetiteurs', '0003_reglagecandidature_candidature_historiquecandidature'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='candidature',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='candidatures_repetiteur', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Compte (facultatif)'),
        ),
        migrations.AddField(
            model_name='candidature',
            name='jeton',
            field=models.CharField(default='', editable=False, max_length=64, verbose_name='Jeton du lien de suivi'),
            preserve_default=False,
        ),
        migrations.RunPython(remplir, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='candidature',
            name='jeton',
            field=models.CharField(default=Repetiteurs.models._jeton, editable=False, max_length=64, unique=True,
                                   verbose_name='Jeton du lien de suivi'),
        ),
    ]
