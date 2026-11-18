"""P14: the Docker stack must run the scheduled jobs, and the scheduler must run exactly the jobs the deployment guide lists."""
import re
from datetime import date
from pathlib import Path
from unittest import mock

from django.core.management import call_command, get_commands
from django.test import SimpleTestCase

from core.management.commands import run_scheduler

ROOT = Path(__file__).resolve().parent.parent.parent
ALL_JOBS = run_scheduler.FREQUENT + run_scheduler.DAILY


def run(rounds=1, today=date(2026, 6, 1), fail=()):
    """Run `rounds` rounds of the scheduler loop with a fake clock; returns the job names in the order they ran."""
    calls = []

    def fake_call(name, **kw):
        calls.append(name)
        if name in fail:
            raise RuntimeError("boom")

    sleeps = []

    def fake_sleep(_):
        sleeps.append(1)
        if len(sleeps) >= rounds:
            raise KeyboardInterrupt  # ends the otherwise endless loop

    day = iter(today if isinstance(today, list) else [today] * rounds)
    with mock.patch.object(run_scheduler, "call_command", fake_call), mock.patch.object(run_scheduler.time, "sleep", fake_sleep), \
         mock.patch.object(run_scheduler.timezone, "localdate", lambda: next(day)), mock.patch.object(run_scheduler, "close_old_connections"):
        try:
            call_command("run_scheduler", interval=1)
        except KeyboardInterrupt:
            pass
    return calls


class SchedulerTests(SimpleTestCase):
    def test_every_job_it_runs_is_a_real_command(self):
        self.assertEqual(sorted(set(ALL_JOBS) - set(get_commands())), [])

    def test_it_runs_the_five_jobs_of_the_deployment_guide(self):
        guide = (ROOT / "docs" / "DEPLOYMENT.md").read_text(encoding="utf-8")
        listed = set(re.findall(r"`python manage\.py (\w+)`", guide.split("## 4. Scheduled jobs")[1].split("## 5.")[0]))
        self.assertEqual(listed - {"run_scheduler"}, set(ALL_JOBS))  # the guide also names the scheduler itself

    def test_notifications_every_round_and_the_daily_jobs_once_per_day(self):
        calls = run(rounds=3)
        self.assertEqual(calls.count("process_notifications"), 3)
        for name in run_scheduler.DAILY:
            self.assertEqual(calls.count(name), 1, name)

    def test_the_daily_jobs_run_again_on_a_new_day(self):
        calls = run(rounds=3, today=[date(2026, 6, 1), date(2026, 6, 1), date(2026, 6, 2)])
        for name in run_scheduler.DAILY:
            self.assertEqual(calls.count(name), 2, name)

    def test_a_failing_job_does_not_stop_the_others_and_is_retried_next_round(self):
        with self.assertLogs("scheduler", level="ERROR"):
            calls = run(rounds=2, fail={"check_overdue_payments"})
        self.assertEqual(calls.count("check_overdue_payments"), 2)  # failed, so not marked done: tried again
        self.assertEqual(calls.count("lead_reminders"), 1)  # the others ran once and were marked done
        self.assertEqual(calls.count("process_notifications"), 2)


class ComposeSchedulerTests(SimpleTestCase):
    def test_compose_has_a_scheduler_service_that_shares_the_backend_environment(self):
        text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        block = re.search(r"^  scheduler:\n(.*?)(?=^  \w|^\w)", text, re.M | re.S)
        self.assertIsNotNone(block, "docker-compose.yml needs a scheduler service")
        scheduler = block.group(1)
        self.assertIn('command: ["python", "manage.py", "run_scheduler"]', scheduler)
        self.assertIn("environment: *backend-env", scheduler)  # the same variables as the backend: database, secret key, time zone
        self.assertIn("&backend-env", text)
        self.assertNotIn("ports:", scheduler)
        self.assertIn("healthcheck: {disable: true}", scheduler)  # the image's HEALTHCHECK probes a web server this container lacks
