from django.db import migrations


def apply_default_price(apps, schema_editor):
    """Actualité, offre d'emploi et publicité : prix unique de 2 500 FCFA (modifiable dans « Réglages du site »)."""
    ServicePlan = apps.get_model('Emploi', 'ServicePlan')
    ServicePlan.objects.filter(kind__in=('news', 'job', 'ad'), quote_only=False).update(price=2500, price_from=False)


class Migration(migrations.Migration):
    dependencies = [
        ('Emploi', '0018_device_tokens'),
        ('core', '0012_publication_price'),
    ]
    operations = [migrations.RunPython(apply_default_price, migrations.RunPython.noop)]
