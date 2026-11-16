"""Documents filed before versions existed become versions, newest carrying the item state; going back removes them."""
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE = [("operations", "0004_kyc_versions_and_staffing")]
AFTER = [("operations", "0005_backfill_kyc_versions")]


class BackfillKycTests(TransactionTestCase):
    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def test_forward_and_back(self):
        apps = self.migrate(BEFORE)
        User, Client, Item = (apps.get_model(a, m) for a, m in (("accounts", "User"), ("clients", "Client"), ("operations", "ChecklistItem")))
        Attachment = apps.get_model("files", "Attachment")
        boss = User.objects.create(email="b@x.com", full_name="B", password="x")
        client = Client.objects.create(company_name="Co", created_by=boss)
        item = Item.objects.create(client=client, name_en="Licence", name_ar="رخصة", status="verified", verified_by=boss)
        ct = ContentType.objects.get(app_label="operations", model="checklistitem")
        for name in ("old.pdf", "new.pdf"):
            Attachment.objects.create(file=name, original_name=name, content_type_header="application/pdf", size=1, category="kyc", uploaded_by=boss, content_type_id=ct.pk, object_id=item.pk)
        apps = self.migrate(AFTER)
        rows = list(apps.get_model("operations", "ChecklistItemVersion").objects.order_by("number").values_list("number", "filename", "state"))
        self.assertEqual(rows, [(1, "old.pdf", "superseded"), (2, "new.pdf", "verified")])
        apps = self.migrate(BEFORE)
        self.assertEqual(apps.get_model("operations", "ChecklistItemVersion").objects.count(), 0)
