"""Fix 5: removing the old contract meeting fields loses nothing and can be undone."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [("contracts", "0004_templates_and_states")]
AFTER = [("contracts", "0005_remove_old_meeting_fields")]


class RemoveOldMeetingFieldsTests(TransactionTestCase):
    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def seed(self):
        executor = MigrationExecutor(connection)
        executor.migrate(BEFORE)
        apps = executor.loader.project_state(BEFORE).apps
        User, Lead, Contract = apps.get_model("accounts", "User"), apps.get_model("leads", "Lead"), apps.get_model("contracts", "Contract")
        boss = User.objects.create(email="boss@x.com", full_name="Boss", password="x")
        made = {}
        for ref, notes, day in (("CT-0001", "Visited the office, agreed scope", "2026-03-04"), ("CT-0002", "", None)):
            lead = Lead.objects.create(ref=f"LD-{ref[-4:]}", company_name=f"Co {ref}", phone=f"07900000{ref[-2:]}", created_by=boss)
            made[ref] = Contract.objects.create(
                ref=ref, lead=lead, requested_by=boss, status="with_commercial", meeting_notes=notes, meeting_date=day, meeting_by=boss if notes else None,
            ).pk
        return made

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def test_notes_are_kept_in_the_history_then_the_fields_go(self):
        made = self.seed()
        apps = self.migrate(AFTER)
        Contract = apps.get_model("contracts", "Contract")
        self.assertEqual({f.name for f in Contract._meta.get_fields()} & {"meeting_notes", "meeting_date", "meeting_by"}, set())
        Audit, CT = apps.get_model("audit", "AuditEntry"), apps.get_model("contenttypes", "ContentType")
        ct = CT.objects.get(app_label="contracts", model="contract")
        entries = list(Audit.objects.filter(content_type=ct, action="meeting_archived"))
        self.assertEqual([(e.object_id, e.to_value, e.comment) for e in entries], [(made["CT-0001"], "2026-03-04", "Visited the office, agreed scope")])
        self.assertEqual(Contract.objects.get(pk=made["CT-0002"]).status, "with_commercial")

    def test_going_back_restores_the_fields_from_the_history(self):
        made = self.seed()
        self.migrate(AFTER)
        apps = self.migrate(BEFORE)
        c = apps.get_model("contracts", "Contract").objects.get(pk=made["CT-0001"])
        self.assertEqual((c.meeting_notes, c.meeting_date.isoformat(), c.meeting_by_id is not None), ("Visited the office, agreed scope", "2026-03-04", True))
        empty = apps.get_model("contracts", "Contract").objects.get(pk=made["CT-0002"])
        self.assertEqual((empty.meeting_notes, empty.meeting_date), ("", None))

    def test_the_old_state_is_gone_from_the_application(self):
        from contracts.models import Contract
        from leads.access import OPEN_CONTRACT

        self.assertNotIn("meeting_logged", Contract.Status.values)
        self.assertNotIn("meeting_logged", OPEN_CONTRACT)
