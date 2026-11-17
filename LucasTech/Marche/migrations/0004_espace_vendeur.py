import secrets

from django.db import migrations, models

import Marche.models


def codes(apps, schema_editor):
    Vendeur = apps.get_model('Marche', 'Vendeur')
    for v in Vendeur.objects.filter(code=''):
        v.code = secrets.token_urlsafe(12)
        v.save(update_fields=['code'])


class Migration(migrations.Migration):

    dependencies = [
        ('Marche', '0003_demandevendeur_categorievendeur'),
    ]

    operations = [
        migrations.AddField(model_name='vendeur', name='code',
                            field=models.CharField(default='', editable=False, max_length=32, verbose_name='Code du lien'),
                            preserve_default=False),
        migrations.RunPython(codes, migrations.RunPython.noop),
        migrations.AlterField(model_name='vendeur', name='code',
                              field=models.CharField(default=Marche.models._code_espace, editable=False, max_length=32,
                                                     unique=True, verbose_name='Code du lien')),
        migrations.AddField(model_name='vendeur', name='activation',
                            field=models.CharField(blank=True, editable=False, max_length=64)),
        migrations.AddField(model_name='vendeur', name='logo',
                            field=models.ImageField(blank=True, upload_to='vendeurs/logos/', verbose_name='Logo')),
        migrations.AddField(model_name='vendeur', name='telephone',
                            field=models.CharField(blank=True, max_length=30, verbose_name='Téléphone')),
        migrations.AddField(model_name='vendeur', name='description',
                            field=models.TextField(blank=True, verbose_name='Description')),
    ]
