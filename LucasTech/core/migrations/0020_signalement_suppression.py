from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0019_suppression_lantante_job'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='Signalement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('produit', 'Produit'), ('offre', "Offre d'emploi"), ('vendeur', 'Boutique'), ('actualite', 'Actualité'), ('autre', 'Autre')], max_length=10, verbose_name='Type')),
                ('objet_id', models.PositiveIntegerField(blank=True, null=True, verbose_name="Numéro de l'élément")),
                ('titre', models.CharField(blank=True, max_length=200, verbose_name='Élément')),
                ('url', models.CharField(blank=True, max_length=300, verbose_name='Adresse')),
                ('motif', models.CharField(choices=[('arnaque', 'Arnaque ou tromperie'), ('interdit', 'Produit interdit ou dangereux'), ('inapproprie', 'Contenu choquant ou inapproprié'), ('faux', 'Informations fausses'), ('autre', 'Autre')], max_length=12, verbose_name='Motif')),
                ('details', models.TextField(blank=True, verbose_name='Précisions')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='E-mail')),
                ('statut', models.CharField(choices=[('nouveau', 'Nouveau'), ('traite', 'Traité'), ('rejete', 'Sans suite')], db_index=True, default='nouveau', max_length=8, verbose_name='Statut')),
                ('note', models.TextField(blank=True, verbose_name="Note de l'équipe")),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Reçu le')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Compte')),
            ],
            options={'verbose_name': 'Signalement', 'verbose_name_plural': 'Signalements', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='DemandeSuppressionCompte',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254, verbose_name='E-mail du compte')),
                ('motif', models.TextField(blank=True, verbose_name='Motif (facultatif)')),
                ('origine', models.CharField(default='site', max_length=10, verbose_name='Envoyée depuis')),
                ('statut', models.CharField(choices=[('nouvelle', 'Nouvelle'), ('traitee', 'Compte supprimé'), ('annulee', 'Annulée')], db_index=True, default='nouvelle', max_length=10, verbose_name='Statut')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Reçue le')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Compte')),
            ],
            options={'verbose_name': 'Demande de suppression de compte', 'verbose_name_plural': 'Demandes de suppression de compte', 'ordering': ['-created_at']},
        ),
    ]
