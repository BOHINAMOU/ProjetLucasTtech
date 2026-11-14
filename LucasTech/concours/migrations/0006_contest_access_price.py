from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('concours', '0005_aide_case_gratuite')]

    operations = [
        migrations.AddField(
            model_name='contest', name='access_price',
            field=models.PositiveIntegerField(default=1000, help_text="Payé une seule fois : accès à vie à tous les sujets et corrigés de ce concours, années futures comprises.", verbose_name="Prix d'accès (FCFA)"),
        ),
    ]
