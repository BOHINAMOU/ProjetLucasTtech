from django.db import migrations

CATEGORIES = [
    ('Enseignement', 'enseignement', 'fa-chalkboard-user'),
    ('Informatique', 'informatique', 'fa-laptop-code'),
    ('Santé', 'sante', 'fa-heart-pulse'),
    ('Administration', 'administration', 'fa-landmark'),
    ('Sécurité', 'securite', 'fa-shield-halved'),
]


def seed(apps, schema_editor):
    Cat = apps.get_model('concours', 'ContestCategory')
    for i, (name, slug, icon) in enumerate(CATEGORIES):
        Cat.objects.get_or_create(slug=slug, defaults={'name': name, 'icon': icon, 'order': i})


class Migration(migrations.Migration):
    dependencies = [('concours', '0001_initial')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
