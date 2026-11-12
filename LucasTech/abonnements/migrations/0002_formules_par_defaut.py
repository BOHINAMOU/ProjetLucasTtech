from django.db import migrations

PLANS = [
    dict(code='standard', name='Standard', monthly_price=1000, yearly_price=10000, contest_limit=3,
         is_unlimited=False, is_highlighted=False, order=1),
    dict(code='premium', name='Premium', monthly_price=2000, yearly_price=20000, contest_limit=8,
         is_unlimited=False, is_highlighted=True, order=2),
    dict(code='ultimate', name='Ultimate', monthly_price=3500, yearly_price=35000, contest_limit=None,
         is_unlimited=True, is_highlighted=False, order=3),
]
EXTENSIONS = [(1, 400), (2, 700), (3, 1000)]


def seed(apps, schema_editor):
    Plan = apps.get_model('abonnements', 'SubscriptionPlan')
    Ext = apps.get_model('abonnements', 'ExtensionOption')
    for p in PLANS:
        Plan.objects.get_or_create(code=p['code'], defaults=p)
    for slots, price in EXTENSIONS:
        Ext.objects.get_or_create(slots=slots, defaults={'price': price})


class Migration(migrations.Migration):
    dependencies = [('abonnements', '0001_initial')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
