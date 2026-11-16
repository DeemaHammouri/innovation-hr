from django.core.management.base import BaseCommand

from notifications.processing import process


class Command(BaseCommand):
    help = "Send due reminders (overdue follow-ups, first contacts, upcoming appointments). Run it every few minutes (cron or a scheduler). Idempotent."

    def handle(self, *args, **options):
        counts = process()
        self.stdout.write(f"Notifications sent: {counts['total']} (leads {counts['leads']}, appointments {counts['appointments']})")
