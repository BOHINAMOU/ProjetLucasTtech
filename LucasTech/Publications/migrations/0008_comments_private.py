from django.db import migrations


def make_private(apps, schema_editor):
    apps.get_model('Publications', 'PublicationComment').objects.update(is_hidden=True)


class Migration(migrations.Migration):
    dependencies = [('Publications', '0007_comments_quick_messages')]
    operations = [migrations.RunPython(make_private, migrations.RunPython.noop)]
