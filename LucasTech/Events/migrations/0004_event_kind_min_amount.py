from django.db import migrations, models


def types_par_defaut(apps, schema_editor):
    """Événement sans type de ticket = Soutien ; « Un sourire pour chaque orphelin » = Soutien."""
    Event = apps.get_model('Events', 'Event')
    for e in Event.objects.all():
        if not e.ticket_types.exists() or 'orphelin' in (e.title or '').lower():
            e.kind = 'soutien'
            e.save(update_fields=['kind'])


class Migration(migrations.Migration):
    dependencies = [('Events', '0003_tickettype_image_alter_tickettype_description')]

    operations = [
        migrations.AddField(
            model_name='event', name='kind',
            field=models.CharField(choices=[('tickets', 'Tickets'), ('soutien', 'Soutien (don)')], default='tickets',
                                   help_text="Tickets : vente de places. Soutien : chacun donne le montant qu'il veut.",
                                   max_length=10, verbose_name='Type'),
        ),
        migrations.AddField(
            model_name='event', name='min_amount',
            field=models.PositiveIntegerField(default=100, verbose_name='Montant minimal du soutien (FCFA)'),
        ),
        migrations.RunPython(types_par_defaut, migrations.RunPython.noop),
    ]
