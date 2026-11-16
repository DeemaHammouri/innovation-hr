"""Tasks made before periods existed get their due date as period; the old per-date uniqueness is replaced by (rule, version, period)."""
from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [("operations", "0006_recurrence_versions_and_holidays")]
AFTER = [("operations", "0008_task_period_required")]


class PeriodBackfillTests(TransactionTestCase):
    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def test_existing_tasks_get_their_due_date_as_period(self):
        apps = self.migrate(BEFORE)
        User, Client, Rule, Task = (apps.get_model(a, m) for a, m in (("accounts", "User"), ("clients", "Client"), ("operations", "RecurringTask"), ("operations", "TaskInstance")))
        boss = User.objects.create(email="b@x.com", full_name="B", password="x")
        client = Client.objects.create(company_name="Co", created_by=boss)
        rule = Rule.objects.create(client=client, title="T", frequency="monthly", start_date=date(2026, 1, 31), next_due=date(2026, 3, 31), created_by=boss)
        Task.objects.create(recurring=rule, client=client, title="T", due_date=date(2026, 1, 31))
        Task.objects.create(recurring=rule, client=client, title="T", due_date=date(2026, 2, 28))
        apps = self.migrate(AFTER)
        rows = list(apps.get_model("operations", "TaskInstance").objects.order_by("due_date").values_list("due_date", "period", "rule_version"))
        self.assertEqual(rows, [(date(2026, 1, 31), date(2026, 1, 31), 1), (date(2026, 2, 28), date(2026, 2, 28), 1)])
