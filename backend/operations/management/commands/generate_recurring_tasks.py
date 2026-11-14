from django.core.management.base import BaseCommand

from operations import reminders, services


class Command(BaseCommand):
    help = "Create the recurring client tasks that are due, and send overdue reminders. Safe to run as often as you like; schedule it once a day."

    def handle(self, *args, **options):
        made = services.generate_due()
        late = reminders.overdue_tasks() + reminders.overdue_meetings()
        self.stdout.write(f"Tasks created: {made}. Reminders sent: {late}.")
