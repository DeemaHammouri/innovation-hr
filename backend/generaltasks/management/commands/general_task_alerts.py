from django.core.management.base import BaseCommand

from generaltasks import reminders


class Command(BaseCommand):
    help = "Send the overdue alerts for general tasks (one per deadline). Safe to run as often as you like; schedule it once a day."

    def handle(self, *args, **options):
        self.stdout.write(f"Task alerts sent: {reminders.overdue_alerts()}.")
