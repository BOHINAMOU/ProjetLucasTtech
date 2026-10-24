from django.db import migrations


def make_private(apps, schema_editor):
    apps.get_model('Emploi', 'FeedComment').objects.update(is_hidden=True)


class Migration(migrations.Migration):
    dependencies = [('Emploi', '0021_comment_moderation_label')]
    operations = [migrations.RunPython(make_private, migrations.RunPython.noop)]
