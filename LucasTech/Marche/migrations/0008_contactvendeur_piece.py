import Marche.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Marche', '0007_minisite')]
    operations = [
        migrations.AlterField('contactvendeur', 'nom', models.CharField(max_length=120, verbose_name='Nom')),
        migrations.AddField('contactvendeur', 'prenom', models.CharField(blank=True, max_length=120, verbose_name='Prénom')),
        migrations.AlterField('contactvendeur', 'categorie', models.CharField(blank=True, choices=[('vetements', 'Vêtements'), ('chaussures', 'Chaussures'), ('accessoires', 'Accessoires'), ('electronique', 'Électronique'), ('livres', 'Livres'), ('alimentation', 'Alimentation'), ('beaute', 'Beauté'), ('autre', 'Autre')], max_length=20, verbose_name='Ce que vous vendez')),
        migrations.AddField('contactvendeur', 'piece_type', models.CharField(blank=True, choices=[('cni', "Carte d'identité"), ('electeur', "Carte d'électeur"), ('passeport', 'Passeport'), ('permis', 'Permis de conduire')], max_length=10, verbose_name='Type de pièce')),
        migrations.AddField('contactvendeur', 'piece', models.FileField(blank=True, storage=Marche.models._prive, upload_to=Marche.models.nom_piece_contact, verbose_name="Pièce d'identité")),
        migrations.AddField('contactvendeur', 'piece_verifiee', models.BooleanField(default=False, verbose_name='Pièce vérifiée')),
        migrations.AddField('contactvendeur', 'consentement', models.BooleanField(default=False, verbose_name='Accord pour la vérification de la pièce')),
    ]
