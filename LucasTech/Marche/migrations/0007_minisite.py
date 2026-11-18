from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('Marche', '0006_contactvendeur')]
    operations = [
        migrations.AddField('vendeur', 'banniere', models.ImageField(blank=True, upload_to='vendeurs/bannieres/', verbose_name='Image de bannière')),
        migrations.AddField('vendeur', 'slogan', models.CharField(blank=True, max_length=140, verbose_name="Phrase d'accueil")),
        migrations.AddField('vendeur', 'couleur', models.CharField(default='#0F6B3E', help_text='Code couleur, ex. #0F6B3E', max_length=7, verbose_name='Couleur principale')),
        migrations.AddField('vendeur', 'email_contact', models.EmailField(blank=True, max_length=254, verbose_name='E-mail de contact')),
        migrations.AddField('vendeur', 'facebook', models.URLField(blank=True, verbose_name='Facebook')),
        migrations.AddField('vendeur', 'instagram', models.URLField(blank=True, verbose_name='Instagram')),
        migrations.AddField('vendeur', 'tiktok', models.URLField(blank=True, verbose_name='TikTok')),
        migrations.CreateModel(
            name='SectionSite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titre', models.CharField(max_length=120, verbose_name='Titre')),
                ('texte', models.TextField(blank=True, verbose_name='Texte')),
                ('image', models.ImageField(blank=True, upload_to='vendeurs/sections/', verbose_name='Image')),
                ('ordre', models.PositiveSmallIntegerField(default=0, verbose_name='Ordre')),
                ('vendeur', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='Marche.vendeur')),
            ],
            options={'verbose_name': 'Section du site', 'verbose_name_plural': 'Sections du site', 'ordering': ['ordre', 'pk']},
        ),
    ]
