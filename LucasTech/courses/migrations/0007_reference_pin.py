"""Référence unique des courses (LX-XXXXXX, aussi pour les courses existantes) et code PIN du solde."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import courses.models


def remplir(apps, schema_editor):
    Course = apps.get_model('courses', 'Course')
    pris = set()
    for c in Course.objects.filter(reference__isnull=True):
        ref = courses.models.nouvelle_reference()
        while ref in pris:
            ref = courses.models.nouvelle_reference()
        pris.add(ref)
        c.reference = ref
        c.save(update_fields=['reference'])


class Migration(migrations.Migration):
    dependencies = [
        ('courses', '0006_zone_grand_lome'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(model_name='course', name='reference',
                            field=models.CharField(max_length=12, null=True, verbose_name='Référence')),
        migrations.RunPython(remplir, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='course', name='reference',
            field=models.CharField(default=courses.models.nouvelle_reference, max_length=12, unique=True,
                                   help_text='Code unique de la course (ex. LX-7K3Q9A).', verbose_name='Référence')),
        migrations.CreateModel(
            name='PinSolde',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pin_hash', models.CharField(blank=True, editable=False, max_length=128)),
                ('essais', models.PositiveSmallIntegerField(default=0, verbose_name='Essais faux')),
                ('bloque_jusqua', models.DateTimeField(blank=True, null=True, verbose_name="Bloqué jusqu'à")),
                ('code_hash', models.CharField(blank=True, editable=False, max_length=128)),
                ('code_envoye_le', models.DateTimeField(blank=True, editable=False, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='pin_solde',
                                              to=settings.AUTH_USER_MODEL, verbose_name='Utilisateur')),
            ],
            options={'verbose_name': 'Code PIN du solde', 'verbose_name_plural': 'Codes PIN du solde'},
        ),
    ]
