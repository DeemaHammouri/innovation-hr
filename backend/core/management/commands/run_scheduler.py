"""The scheduler container: runs every scheduled job of docs/DEPLOYMENT.md without cron.

`process_notifications` every few minutes (the 60-minute urgent alerts depend on it) and the four daily jobs once per local day.
Every job is idempotent, so a failed job is simply tried again on the next round and a restart repeats nothing harmful.
"""
import logging
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

log = logging.getLogger("scheduler")

FREQUENT = ["process_notifications"]
DAILY = ["generate_recurring_tasks", "check_overdue_payments", "general_task_alerts", "lead_reminders"]


class Command(BaseCommand):
    help = "Run the scheduled jobs forever: process_notifications every --interval seconds, the daily jobs once per local day. --once does a single round."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=int, default=300, help="seconds between rounds (default 300 = 5 minutes)")
        parser.add_argument("--once", action="store_true", help="run one round and exit")

    def run_job(self, name):
        try:
            call_command(name, stdout=self.stdout)
            return True
        except Exception:  # one broken job must not stop the others, or the loop
            log.exception("scheduled job %s failed; it will be tried again on the next round", name)
            return False

    def handle(self, *args, interval=300, once=False, **options):
        done = {}  # job name -> the local day it last succeeded
        while True:
            close_old_connections()  # a container that lives for weeks outlives its database connection
            for name in FREQUENT:
                self.run_job(name)
            today = timezone.localdate()
            for name in DAILY:
                if done.get(name) != today and self.run_job(name):
                    done[name] = today
            if once:
                return
            time.sleep(interval)
