"""Contracts handed over before handovers existed get an accepted handover and a project; going back removes only those."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [("operations", "0002_handover_and_project"), ("contracts", "0005_remove_old_meeting_fields")]
AFTER = [("operations", "0003_backfill_handovers")]


class BackfillTests(TransactionTestCase):
    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def seed(self):
        executor = MigrationExecutor(connection)
        executor.migrate(BEFORE)
        apps = executor.loader.project_state(BEFORE).apps
        User, Lead, Contract, Client = (apps.get_model(a, m) for a, m in (("accounts", "User"), ("leads", "Lead"), ("contracts", "Contract"), ("clients", "Client")))
        boss = User.objects.create(email="boss@x.com", full_name="Boss", password="x")
        out = {}
        for ref, status in (("CT-0001", "handed_over"), ("CT-0002", "signed")):
            lead = Lead.objects.create(ref=f"LD-{ref[-4:]}", company_name=f"Co {ref}", phone=f"07900000{ref[-2:]}", created_by=boss)
            client = Client.objects.create(company_name=f"Co {ref}", created_by=boss, status="active")
            out[ref] = Contract.objects.create(ref=ref, lead=lead, client=client, requested_by=boss, status=status, handed_over_by=boss).pk
        return out

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def test_only_handed_over_contracts_get_an_accepted_handover_and_one_project(self):
        made = self.seed()
        apps = self.migrate(AFTER)
        Handover, Project = apps.get_model("operations", "Handover"), apps.get_model("operations", "Project")
        rows = list(Handover.objects.values_list("contract_id", "status", "ref"))
        self.assertEqual([(c, s) for c, s, _ in rows], [(made["CT-0001"], "accepted")])
        self.assertTrue(rows[0][2].startswith("HO-"))
        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(Project.objects.get().handover.contract_id, made["CT-0001"])

    def test_going_back_removes_what_the_migration_made(self):
        self.seed()
        self.migrate(AFTER)
        apps = self.migrate(BEFORE)
        self.assertEqual((apps.get_model("operations", "Handover").objects.count(), apps.get_model("operations", "Project").objects.count()), (0, 0))
