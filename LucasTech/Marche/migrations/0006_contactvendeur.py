from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('Marche', '0005_vendeur_slug')]
    operations = [
        migrations.CreateModel(
            name='ContactVendeur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('statut', models.CharField(choices=[('nouvelle', 'Nouvelle'), ('contactee', 'Contactée'), ('compte_cree', 'Compte créé'), ('refusee', 'Refusée')], db_index=True, default='nouvelle', max_length=12, verbose_name='Statut')),
                ('boutique', models.CharField(max_length=120, verbose_name='Nom de la boutique')),
                ('nom', models.CharField(max_length=120, verbose_name='Votre nom')),
                ('telephone', models.CharField(max_length=20, verbose_name='Téléphone / WhatsApp')),
                ('email', models.EmailField(max_length=254, verbose_name='E-mail')),
                ('ville', models.CharField(max_length=80, verbose_name='Ville')),
                ('categorie', models.CharField(choices=[('vetements', 'Vêtements'), ('chaussures', 'Chaussures'), ('accessoires', 'Accessoires'), ('electronique', 'Électronique'), ('livres', 'Livres'), ('alimentation', 'Alimentation'), ('beaute', 'Beauté'), ('autre', 'Autre')], max_length=20, verbose_name='Ce que vous vendez')),
                ('message', models.TextField(blank=True, verbose_name='Message')),
                ('note', models.TextField(blank=True, verbose_name="Note de l'équipe")),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Reçue le')),
                ('vendeur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contacts', to='Marche.vendeur', verbose_name='Vendeur créé')),
            ],
            options={'verbose_name': 'Demande de contact vendeur', 'verbose_name_plural': 'Demandes de contact vendeurs', 'ordering': ['-created_at']},
        ),
    ]
