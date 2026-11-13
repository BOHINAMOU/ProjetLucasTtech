from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Publications', '0009_publicationcomment_is_read_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='publication',
            name='show_on_site',
            field=models.BooleanField(default=True, verbose_name='Publier sur le site'),
        ),
        migrations.AddField(
            model_name='publication',
            name='show_in_app',
            field=models.BooleanField(default=True, verbose_name="Publier dans l'application"),
        ),
    ]
