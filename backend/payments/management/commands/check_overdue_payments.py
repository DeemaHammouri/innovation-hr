from django.core.management.base import BaseCommand

from payments import services


class Command(BaseCommand):
    help = "Remind the Commercial head and the CEO about instalments that have gone overdue. Idempotent; schedule it once a day."

    def handle(self, *args, **options):
        self.stdout.write(f"Reminders sent: {services.overdue_reminders()}.")
