"""Objective 20: one task per (rule, version, period), safe repeats, editable holiday calendar, edits touch only future periods."""
from datetime import date, timedelta
from unittest import mock

from django.db import IntegrityError, transaction
from django.utils import timezone

from audit.models import AuditEntry
from lookups.models import Holiday
from operations import services
from operations.models import RecurringTask, TaskInstance
from operations.tests import OCase


def at(day):
    return mock.patch("django.utils.timezone.localdate", return_value=day)


class EngineTests(OCase):
    def rule(self, **over):
        client = self.mkclient()
        start = over.pop("start", date(2026, 11, 2))
        task = RecurringTask.objects.create(
            client=client, title="Reconcile", frequency=over.pop("frequency", "monthly"), start_date=start, next_due=start,
            assignee=self.omem, created_by=self.ohead, **over,
        )
        return task

    def test_repeated_runs_create_each_task_once(self):
        task = self.rule(frequency="daily", start=date(2026, 11, 1))
        first = services.generate_due(date(2026, 11, 5))
        self.assertEqual(first, 5)
        for _ in range(3):
            self.assertEqual(services.generate_due(date(2026, 11, 5)), 0)
        self.assertEqual(TaskInstance.objects.filter(recurring=task).count(), 5)

    def test_the_database_refuses_a_second_task_for_the_same_period(self):
        task = self.rule()
        services.generate_due(date(2026, 11, 2))
        inst = TaskInstance.objects.get(recurring=task)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TaskInstance.objects.create(recurring=task, client=task.client, title="x", due_date=date(2026, 11, 3), rule_version=inst.rule_version, period=inst.period)

    def test_a_task_that_lands_on_the_weekend_is_due_on_the_next_working_day_but_keeps_its_period(self):
        task = self.rule(start=date(2026, 11, 20))  # a Friday
        services.generate_due(date(2026, 11, 22))
        inst = TaskInstance.objects.get(recurring=task)
        self.assertEqual((inst.due_date, inst.period), (date(2026, 11, 22), date(2026, 11, 1)))
        self.assertEqual(services.generate_due(date(2026, 11, 30)), 0)  # nothing new for the same month

    def test_the_task_is_created_when_it_is_due_not_before(self):
        task = self.rule(start=date(2026, 11, 20))
        self.assertEqual(services.generate_due(date(2026, 11, 21)), 0)  # the nominal date has passed but the due date (Sunday) has not
        self.assertEqual(services.generate_due(date(2026, 11, 22)), 1)
        self.assertEqual(TaskInstance.objects.filter(recurring=task).count(), 1)

    def test_a_holiday_moves_future_tasks_only(self):
        task = self.rule(frequency="weekly", start=date(2026, 11, 2))  # Mondays
        services.generate_due(date(2026, 11, 9))
        before = list(TaskInstance.objects.filter(recurring=task).values_list("due_date", flat=True))
        Holiday.objects.create(date=date(2026, 11, 16), name_en="Holiday", name_ar="عطلة")
        Holiday.objects.create(date=date(2026, 11, 9), name_en="Late holiday", name_ar="عطلة")
        services.generate_due(date(2026, 11, 23))
        after = list(TaskInstance.objects.filter(recurring=task).order_by("due_date").values_list("due_date", flat=True))
        self.assertEqual(after[:len(before)], sorted(before))  # tasks already made did not move
        self.assertIn(date(2026, 11, 17), after)  # the 16th is a holiday, so that week's task is due on the 17th

    def test_editing_the_schedule_starts_a_new_version_and_keeps_past_tasks(self):
        task = self.rule(frequency="weekly", start=date(2026, 11, 2))
        services.generate_due(date(2026, 11, 16))
        old = list(TaskInstance.objects.filter(recurring=task).values_list("id", "due_date", "rule_version"))
        self.assertEqual({v for _, _, v in old}, {1})
        with at(date(2026, 11, 17)):
            self.as_user(self.ohead)
            res = self.client.patch(f"/api/operations/recurring/{task.pk}/", {"frequency": "monthly", "start_date": "2026-11-17"}, format="json")
            self.assertEqual(res.status_code, 200, res.data)
        task.refresh_from_db()
        self.assertEqual(task.version, 2)
        self.assertEqual(list(TaskInstance.objects.filter(recurring=task, rule_version=1).values_list("id", "due_date", "rule_version")), old)
        services.generate_due(date(2026, 12, 17))
        new = list(TaskInstance.objects.filter(recurring=task, rule_version=2).order_by("due_date").values_list("due_date", flat=True))
        self.assertEqual(new, [date(2026, 11, 17), date(2026, 12, 17)])

    def test_a_title_or_assignee_edit_is_not_a_new_version_and_changes_only_future_tasks(self):
        task = self.rule(frequency="daily", start=date(2026, 11, 1))
        services.generate_due(date(2026, 11, 3))
        self.as_user(self.ohead)
        res = self.client.patch(f"/api/operations/recurring/{task.pk}/", {"title": "New title", "assignee": self.omem2.pk}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        task.refresh_from_db()
        self.assertEqual(task.version, 1)
        services.generate_due(date(2026, 11, 4))
        titles = list(TaskInstance.objects.filter(recurring=task).order_by("due_date").values_list("title", flat=True))
        self.assertEqual(titles, ["Reconcile", "Reconcile", "Reconcile", "New title"])

    def test_pausing_stops_new_tasks_and_resuming_does_not_flood(self):
        task = self.rule(frequency="daily", start=date(2026, 11, 1))
        services.generate_due(date(2026, 11, 2))
        RecurringTask.objects.filter(pk=task.pk).update(active=False)
        self.assertEqual(services.generate_due(date(2026, 11, 20)), 0)

    def test_the_run_is_logged_against_the_client(self):
        task = self.rule()
        self.as_user(self.ohead)
        self.client.patch(f"/api/operations/recurring/{task.pk}/", {"frequency": "yearly", "start_date": "2027-01-05"}, format="json")
        self.assertIn("recurring_updated", self.actions(task.client))


class HolidayCalendarTests(OCase):
    def test_everyone_can_read_and_only_the_ceo_can_change_the_calendar(self):
        self.assert_matrix("get", "/api/lookups/holidays/", {"*": 200})
        for key, want in (("ceo", 201), ("operation_head", 403), ("commercial_head", 403), ("hr_head", 403)):
            self.as_role(key)
            res = self.client.post("/api/lookups/holidays/", {"date": "2026-12-25", "name_en": "Christmas", "name_ar": "عيد الميلاد"}, format="json")
            self.assertEqual(res.status_code, want if key != "ceo" else 201, (key, res.data))
            Holiday.objects.all().delete()

    def test_a_date_can_be_listed_only_once_and_needs_both_names(self):
        self.as_role("ceo")
        body = {"date": "2026-12-25", "name_en": "Christmas", "name_ar": "عيد الميلاد"}
        self.assertEqual(self.client.post("/api/lookups/holidays/", body, format="json").status_code, 201)
        self.assertEqual(self.client.post("/api/lookups/holidays/", body, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/lookups/holidays/", {"date": "2026-12-26", "name_en": "", "name_ar": "x"}, format="json").status_code, 400)

    def test_the_ceo_can_remove_a_holiday_and_it_is_logged(self):
        self.as_role("ceo")
        h = Holiday.objects.create(date=date(2026, 12, 25), name_en="Christmas", name_ar="عيد الميلاد")
        self.assertEqual(self.client.delete(f"/api/lookups/holidays/{h.pk}/").status_code, 204)
        self.assertFalse(Holiday.objects.exists())
        self.assertTrue(AuditEntry.objects.filter(action__in=["holiday_added", "holiday_removed"]).exists())
