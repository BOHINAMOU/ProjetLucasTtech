from django.db import migrations


def set_account_types(apps, schema_editor):
    """Comptes existants : le type de compte se déduit du profil déjà créé (entreprise ou candidat)."""
    User = apps.get_model('Users', 'User')
    EmployerProfile = apps.get_model('Emploi', 'EmployerProfile')
    CandidateProfile = apps.get_model('Emploi', 'CandidateProfile')
    User.objects.filter(pk__in=EmployerProfile.objects.values('user_id')).update(account_type='employer')
    User.objects.filter(pk__in=CandidateProfile.objects.values('user_id')).exclude(account_type='employer') \
        .update(account_type='candidate')


class Migration(migrations.Migration):

    dependencies = [
        ('Emploi', '0014_candidate_boost_spontaneous'),
        ('Users', '0008_account_type'),
    ]

    operations = [
        migrations.RunPython(set_account_types, migrations.RunPython.noop),
    ]
