"""P28: the database itself refuses to change or delete an audit row, whatever the application does."""
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, TransactionTestCase

from accounts.models import User
from audit.models import AuditEntry


def make_entry():
    user = User.objects.create_user(email="a@x.com", password="x", full_name="A")
    return AuditEntry.objects.create(actor=user, content_type=ContentType.objects.get_for_model(User), object_id=user.pk, action="update", comment="original")


class RawSqlTests(TestCase):
    def test_raw_update_is_refused(self):
        entry = make_entry()
        with self.assertRaisesMessage(DatabaseError, "append-only"), transaction.atomic(), connection.cursor() as cur:
            cur.execute("UPDATE audit_auditentry SET comment = %s WHERE id = %s", ["tampered-by-sql", entry.pk])
        self.assertEqual(AuditEntry.objects.get(pk=entry.pk).comment, "original")

    def test_raw_delete_is_refused(self):
        entry = make_entry()
        with self.assertRaisesMessage(DatabaseError, "append-only"), transaction.atomic(), connection.cursor() as cur:
            cur.execute("DELETE FROM audit_auditentry WHERE id = %s", [entry.pk])
        self.assertTrue(AuditEntry.objects.filter(pk=entry.pk).exists())

    def test_raw_delete_of_everything_is_refused(self):
        make_entry()
        with self.assertRaisesMessage(DatabaseError, "append-only"), transaction.atomic(), connection.cursor() as cur:
            cur.execute("DELETE FROM audit_auditentry")
        self.assertEqual(AuditEntry.objects.count(), 1)

    def test_inserting_still_works(self):
        make_entry()
        self.assertEqual(AuditEntry.objects.count(), 1)


class FlushStillWorksTests(TransactionTestCase):
    """The test database can still be emptied between tests (SQLite: through the test backend; PostgreSQL: TRUNCATE)."""

    def test_the_first_test_leaves_a_row_the_flush_must_remove(self):
        make_entry()
        self.assertEqual(AuditEntry.objects.count(), 1)

    def test_the_next_test_starts_empty_and_the_trigger_is_back(self):
        self.assertEqual(AuditEntry.objects.count(), 0)
        entry = make_entry()
        with self.assertRaisesMessage(DatabaseError, "append-only"), transaction.atomic(), connection.cursor() as cur:
            cur.execute("DELETE FROM audit_auditentry WHERE id = %s", [entry.pk])
