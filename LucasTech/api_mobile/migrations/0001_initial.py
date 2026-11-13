from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def concours_category(apps, schema_editor):
    """Catégorie « Concours » pour les annonces (onglet Annonces des concours dans l'appli)."""
    Cat = apps.get_model('Publications', 'PublicationCategory')
    if not Cat.objects.filter(slug='concours').exists():
        Cat.objects.create(name='Concours', slug='concours', icon='fa-file-pen', order=0)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('Publications', '0009_publicationcomment_is_read_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='OfflineDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('epreuve', 'Sujet'), ('corrige', 'Corrigé')], max_length=10,
                                          verbose_name='Type')),
                ('doc_id', models.PositiveIntegerField(verbose_name='Document')),
                ('titre', models.CharField(blank=True, max_length=200, verbose_name='Titre')),
                ('sous_titre', models.CharField(blank=True, max_length=200, verbose_name='Sous-titre')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Enregistré le')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                           related_name='offline_documents', to=settings.AUTH_USER_MODEL,
                                           verbose_name='Utilisateur')),
            ],
            options={'verbose_name': 'Document hors connexion', 'verbose_name_plural': 'Documents hors connexion',
                     'ordering': ['-created_at'], 'unique_together': {('user', 'kind', 'doc_id')}},
        ),
        migrations.RunPython(concours_category, migrations.RunPython.noop),
    ]
