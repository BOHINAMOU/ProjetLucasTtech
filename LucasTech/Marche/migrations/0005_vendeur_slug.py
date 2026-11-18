from django.db import migrations, models


def remplir(apps, schema_editor):
    from django.utils.text import slugify
    V = apps.get_model('Marche', 'Vendeur')
    pris = set()
    for v in V.objects.order_by('pk'):
        base = (slugify(v.boutique) or 'boutique')[:120]
        s, i = base, 2
        while s in pris:
            s, i = f'{base}-{i}', i + 1
        pris.add(s)
        v.slug = s
        v.save(update_fields=['slug'])


class Migration(migrations.Migration):
    dependencies = [('Marche', '0004_espace_vendeur')]
    operations = [
        migrations.AddField('vendeur', 'slug', models.SlugField(
            'Adresse de la boutique', max_length=140, unique=True, null=True, blank=True,
            help_text='Lien public : /shop/vendeur/<adresse>/ (rempli automatiquement).')),
        migrations.RunPython(remplir, migrations.RunPython.noop),
        migrations.AddField('vendeur', 'debut_acces', models.DateField("Début de l'accès", null=True, blank=True)),
        migrations.AddField('vendeur', 'fin_acces', models.DateField("Fin de l'accès", null=True, blank=True,
                                                                     help_text='Vide = sans limite.')),
        migrations.AlterField('vendeur', 'statut', models.CharField(
            'Statut', max_length=12, default='en_attente',
            choices=[('en_attente', 'En attente'), ('valide', 'Actif'), ('suspendu', 'Suspendu'), ('expire', 'Expiré')])),
    ]
