from django.core.management.base import BaseCommand

from abonnements.services import expire_overdue


class Command(BaseCommand):
    help = "Passe en « expiré » les abonnements dont la date de fin est dépassée (à lancer chaque jour par cron)."

    def handle(self, *args, **opts):
        n = expire_overdue()
        self.stdout.write(f"{n} abonnement(s) expiré(s).")
