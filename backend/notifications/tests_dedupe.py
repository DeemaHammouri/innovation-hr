"""P15: two callers sending the same reminder at the same moment must produce one notification."""
import threading

from django.db import IntegrityError, connections, transaction
from django.test import TransactionTestCase

from accounts.models import User
from notifications.models import Notification
from notifications.service import notify


class ParallelDedupeTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="n@x.com", password="x", full_name="N")

    def race(self, callers, rounds, key):
        results = []

        def go(round_):
            try:
                results.append(bool(notify(self.user, "followup_overdue", dedupe_key=f"{key}:{round_}", ref="R", name="Co")))
            finally:
                connections.close_all()

        for r in range(rounds):
            barrier = threading.Barrier(callers)

            def worker(r=r):
                barrier.wait()
                go(r)

            threads = [threading.Thread(target=worker) for _ in range(callers)]
            [t.start() for t in threads]
            [t.join() for t in threads]
        return results

    def test_six_simultaneous_callers_per_key_give_one_notification_each(self):
        results = self.race(callers=6, rounds=20, key="followup:1")
        keys = list(Notification.objects.values_list("dedupe_key", flat=True))
        self.assertEqual(len(keys), 20)
        self.assertEqual(len(set(keys)), 20, "a key was delivered twice")
        self.assertEqual(sum(results), 20)  # exactly one caller per key was told it sent something

    def test_the_database_itself_refuses_a_second_row_with_the_same_key(self):
        Notification.objects.create(user=self.user, kind="k", title="t", dedupe_key="same")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notification.objects.create(user=self.user, kind="k", title="t", dedupe_key="same")

    def test_notifications_without_a_key_are_never_deduplicated(self):
        for _ in range(3):
            self.assertIsNotNone(notify(self.user, "followup_overdue", ref="R", name="Co"))
        self.assertEqual(Notification.objects.count(), 3)

    def test_the_same_key_for_two_people_is_fine(self):
        other = User.objects.create_user(email="o@x.com", password="x", full_name="O")
        self.assertIsNotNone(notify(self.user, "followup_overdue", dedupe_key="k", ref="R", name="Co"))
        self.assertIsNotNone(notify(other, "followup_overdue", dedupe_key="k", ref="R", name="Co"))
        self.assertIsNone(notify(self.user, "followup_overdue", dedupe_key="k", ref="R", name="Co"))


class MigrationKeepsDuplicatesTests(TransactionTestCase):
    """Existing databases may already hold double-sent reminders: the migration keeps every row and keeps the key on the first only."""

    def test_duplicate_rows_survive_with_a_blank_key_on_the_copies(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        executor.migrate([("notifications", "0001_initial")])
        old = executor.loader.project_state([("notifications", "0001_initial")]).apps
        user = User.objects.create_user(email="m@x.com", password="x", full_name="M")
        Old = old.get_model("notifications", "Notification")
        ids = [Old.objects.create(user_id=user.pk, kind="k", title="t", dedupe_key="dup").pk for _ in range(3)]
        ids.append(Old.objects.create(user_id=user.pk, kind="k", title="t", dedupe_key="single").pk)

        executor = MigrationExecutor(connection)
        executor.migrate([("notifications", "0002_unique_dedupe_key")])
        rows = dict(Notification.objects.values_list("pk", "dedupe_key"))
        self.assertEqual(sorted(rows), sorted(ids))  # nothing deleted
        self.assertEqual([rows[i] for i in ids], ["dup", "", "", "single"])
