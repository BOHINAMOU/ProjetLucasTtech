from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def existing_accounts_verified(apps, schema_editor):
    """Les comptes créés avant la vérification de l'e-mail sont considérés comme vérifiés."""
    User = apps.get_model('Users', 'User')
    User.objects.filter(is_verified=False).update(is_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ('Users', '0009_member_label'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailVerificationCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=6, verbose_name='Code')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('attempts', models.PositiveSmallIntegerField(default=0, verbose_name='Essais')),
                ('is_used', models.BooleanField(default=False, verbose_name='Utilisé')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_codes',
                                           to=settings.AUTH_USER_MODEL, verbose_name='Utilisateur')),
            ],
            options={'verbose_name': "Code de vérification de l'e-mail",
                     'verbose_name_plural': "Codes de vérification de l'e-mail", 'ordering': ['-created_at']},
        ),
        migrations.RunPython(existing_accounts_verified, migrations.RunPython.noop),
    ]
