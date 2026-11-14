from django.core.management.base import BaseCommand

from leads.reminders import run


class Command(BaseCommand):
    help = "Send overdue follow-up and first-contact reminders. Safe to run as often as you like: each reminder is sent once."

    def handle(self, *args, **options):
        self.stdout.write(f"Reminders sent: {run()}")
