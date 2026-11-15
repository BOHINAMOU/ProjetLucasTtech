"""Rappels de l'abonnement Accès Épreuves : 7 jours avant, 1 jour avant, puis à l'expiration.
À lancer chaque jour (cron). Chaque rappel n'est envoyé qu'une fois (cloche + push)."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Envoie les rappels d'expiration de l'abonnement Accès Épreuves."

    def handle(self, *args, **opts):
        from api_mobile.notifs import notifier
        from abonnements.models import AccesEpreuves
        now = timezone.now()
        n = 0
        # dernière période de chaque client (la plus tardive)
        vus = set()
        for a in AccesEpreuves.objects.filter(fin__gt=now - timedelta(days=2)).order_by('-fin').select_related('user'):
            if a.user_id in vus:
                continue
            vus.add(a.user_id)
            reste = a.fin - now
            if reste <= timedelta(0):
                if not a.rappel_fin:
                    notifier(a.user, "Abonnement expiré", "Renouvelez pour lire les épreuves.")
                    a.rappel_fin = a.rappel_1 = a.rappel_7 = True
                    a.save(update_fields=['rappel_fin', 'rappel_1', 'rappel_7'])
                    n += 1
            elif reste <= timedelta(days=1):
                if not a.rappel_1:
                    notifier(a.user, "Abonnement : dernier jour", "Renouvelez pour garder l'accès.")
                    a.rappel_1 = a.rappel_7 = True
                    a.save(update_fields=['rappel_1', 'rappel_7'])
                    n += 1
            elif reste <= timedelta(days=7):
                if not a.rappel_7:
                    notifier(a.user, "Abonnement : 7 jours restants", f"Fin le {timezone.localtime(a.fin):%d/%m/%Y}.")
                    a.rappel_7 = True
                    a.save(update_fields=['rappel_7'])
                    n += 1
        self.stdout.write(f"{n} rappel(s)")
