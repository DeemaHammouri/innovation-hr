from datetime import date, timedelta
from unittest import mock

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from audit.models import AuditEntry
from clients.models import Client
from contracts import services as contract_services
from contracts.models import Contract
from core.access import content_type_for
from core.roles import ALL_ROLES
from core.testing import RoleCase
from files.models import Attachment
from leads.models import Lead
from lookups.models import ChecklistTemplateItem
from notifications.models import Notification
from operations import reminders, services
from operations.models import ChecklistItem, QAMeeting, RecurringTask, TaskInstance

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
OP = ("operation_head", "operation_member")


class OCase(RoleCase):
    def setUp(self):
        super().setUp()
        self.ceo, self.mkt = self.users["ceo"], self.users["marketing"]
        self.ohead, self.omem = self.users["operation_head"], self.users["operation_member"]
        self.ohead2 = None
        self.omem2 = self.make_user("omem2@x.com", "Operation", "member")
        self.chead, self.cmem = self.users["commercial_head"], self.users["commercial_member"]
        self.hr = self.users["hr_head"]
        self.n = 0
        ChecklistTemplateItem.objects.all().delete()
        self.t1 = ChecklistTemplateItem.objects.create(name_en="Commercial register", name_ar="السجل التجاري", required=True, sort_order=1)
        self.t2 = ChecklistTemplateItem.objects.create(name_en="Tax certificate", name_ar="شهادة الضريبة", required=True, sort_order=2)
        self.t3 = ChecklistTemplateItem.objects.create(name_en="Logo", name_ar="الشعار", required=False, sort_order=3)

    def mkclient(self, status="onboarding", items=True, owner=None):
        self.n += 1
        c = Client.objects.create(company_name=f"Client {self.n}", created_by=self.ceo, status=status)
        if items:
            for pos, t in enumerate(ChecklistTemplateItem.objects.all()):
                ChecklistItem.objects.create(client=c, template_item=t, name_en=t.name_en, name_ar=t.name_ar, required=t.required, position=pos)
        if owner is not None:
            lead = Lead.objects.create(ref=f"LD-6{self.n:03d}", company_name=c.company_name, phone=f"0760000{self.n:03d}", created_by=self.mkt, status="qualified", assigned_to=owner)
            Contract.objects.create(ref=f"CT-6{self.n:03d}", lead=lead, requested_by=owner, client=c, status="handed_over")
        return c

    def upload(self, user, item, name="doc.pdf"):
        self.as_user(user)
        return self.client.post(f"/api/files/?target=checklist_item:{item.pk}", {"file": SimpleUploadedFile(name, PDF, content_type="application/pdf"), "category": "kyc"}, format="multipart")

    def item(self, client, i=0):
        return client.checklist.order_by("position")[i]

    def act(self, user, path, body=None):
        self.as_user(user)
        return self.client.post(f"/api/operations/{path}/", body or {}, format="json")

    def actions(self, client):
        return list(AuditEntry.objects.filter(content_type=content_type_for(Client), object_id=client.pk).order_by("id").values_list("action", flat=True))

    def verified_all(self, client):
        for item in client.checklist.filter(required=True):
            self.upload(self.omem, item)
            self.act(self.omem, f"checklist/{item.pk}/verify")

    def recurring(self, client=None, **over):
        client = client or self.mkclient()
        body = {"client": client.pk, "title": "Monthly reconciliation", "frequency": "monthly", "start_date": timezone.localdate().isoformat(), "assignee": self.omem.pk}
        body.update(over)
        self.as_user(self.ohead)
        return self.client.post("/api/operations/recurring/", body, format="json")


class AccessTests(OCase):
    def test_client_list_access(self):
        self.assert_matrix("get", "/api/operations/clients/", {"ceo": 200, "commercial_head": 200, "commercial_member": 200, "operation_head": 200, "operation_member": 200, "*": 403})

    def test_visibility(self):
        mine, theirs, loose = self.mkclient(owner=self.cmem), self.mkclient(owner=self.make_user("c2@x.com", "Commercial", "member")), self.mkclient()
        self.as_role("commercial_member")
        self.assertEqual({r["id"] for r in self.client.get("/api/operations/clients/").data["results"]}, {mine.pk})
        self.assertEqual(self.client.get(f"/api/operations/clients/{theirs.pk}/").status_code, 404)
        for key in ("ceo", "operation_head", "operation_member"):
            self.as_role(key)
            self.assertEqual(self.client.get("/api/operations/clients/").data["count"], 3, key)
        # The Commercial head is no different from a member: only clients from their own deals, never all of them.
        self.as_role("commercial_head")
        self.assertEqual(self.client.get("/api/operations/clients/").data["count"], 0)
        headmine = self.mkclient(owner=self.chead)
        self.assertEqual({r["id"] for r in self.client.get("/api/operations/clients/").data["results"]}, {headmine.pk})
        self.assertEqual(self.client.get(f"/api/operations/clients/{mine.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/operations/clients/{headmine.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/operations/tasks/?client={mine.pk}").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/comments/?target=client:{mine.pk}").status_code, 404)
        # A contract the head requested counts as theirs even when the lead is assigned to a member.
        Contract.objects.filter(client=mine).update(requested_by=self.chead)
        self.assertEqual(self.client.get(f"/api/operations/clients/{mine.pk}/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/operations/clients/{mine.pk}/cadence/", {"qa_cadence_days": 14}, format="json").status_code, 403)  # still read-only

    def test_write_rules(self):
        c = self.mkclient()
        item = self.item(c)
        self.upload(self.omem, item)
        for key in ALL_ROLES:
            self.as_role(key)
            res = self.client.post(f"/api/operations/checklist/{item.pk}/verify/", {}, format="json")
            if key not in OP:
                self.assertIn(res.status_code, (403, 404), key)
        for key in ("ceo", "commercial_head", "operation_member"):
            self.as_role(key)
            self.assertIn(self.client.post(f"/api/operations/clients/{c.pk}/cadence/", {"qa_cadence_days": 14}, format="json").status_code, (403, 404), key)

    def test_comments_and_files_follow_the_client(self):
        c = self.mkclient(owner=self.cmem)
        other = self.mkclient()
        self.as_role("commercial_member")
        self.assertEqual(self.client.get(f"/api/comments/?target=client:{c.pk}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/comments/?target=client:{other.pk}").status_code, 404)
        self.assertEqual(self.client.post(f"/api/files/?target=client:{c.pk}", {"file": SimpleUploadedFile("a.pdf", PDF)}, format="multipart").status_code, 403)
        item = self.item(c)
        self.assertEqual(self.upload(self.cmem, item).status_code, 403)  # read-only for Commercial
        for key in ("hr_head", "marketing"):
            self.as_role(key)
            self.assertIn(self.client.get(f"/api/comments/?target=client:{c.pk}").status_code, (403, 404), key)

    def test_existing_client_screens_keep_their_rule(self):
        self.as_role("operation_member")
        self.assertEqual(self.client.get("/api/clients/").status_code, 403)  # unchanged: CEO and Operation head only
        self.as_role("operation_head")
        self.assertEqual(self.client.get("/api/clients/").status_code, 200)


class OnboardingTests(OCase):
    def handed_over(self, name="Brand New Co"):
        lead = Lead.objects.create(ref="LD-5001", company_name=name, contact_name="Sam", phone="0750000001", email="s@x.com", created_by=self.mkt, status="qualified", assigned_to=self.cmem, skipped_quotation_at=timezone.now())
        c = contract_services.request_contract(self.cmem, lead)
        Contract.objects.filter(pk=c.pk).update(status="signed", signed_by=self.ceo, signed_at=timezone.now())
        Attachment.objects.create(file=ContentFile(PDF, name="f.pdf"), original_name="f.pdf", content_type_header="application/pdf", size=len(PDF), category="final_signed", uploaded_by=self.hr, content_type=content_type_for(Contract), object_id=c.pk)
        return contract_services.hand_over(self.hr, Contract.objects.get(pk=c.pk))

    def test_handover_creates_client_with_checklist_from_template(self):
        c = self.handed_over()
        client = c.client
        self.assertEqual((client.company_name, client.contact_person, client.status), ("Brand New Co", "Sam", "onboarding"))
        self.assertEqual(list(client.checklist.values_list("name_en", "required")), [("Commercial register", True), ("Tax certificate", True), ("Logo", False)])
        self.assertIn("created", self.actions(client))

    def test_handover_links_an_existing_client_by_name(self):
        existing = Client.objects.create(company_name="brand new co", created_by=self.ceo)
        c = self.handed_over()
        self.assertEqual(c.client_id, existing.pk)
        self.assertEqual(Client.objects.count(), 1)

    def test_inactive_template_items_are_not_copied(self):
        ChecklistTemplateItem.objects.filter(pk=self.t3.pk).update(is_active=False)
        self.assertEqual(self.handed_over().client.checklist.count(), 2)

    def test_client_becomes_active_only_when_required_items_are_satisfied(self):
        client = self.mkclient()
        a, b, optional = (self.item(client, i) for i in range(3))
        self.assertEqual(self.upload(self.omem, a).status_code, 201)
        a.refresh_from_db()
        self.assertEqual(a.status, "uploaded")
        self.assertEqual(self.act(self.omem, f"checklist/{a.pk}/verify").data["status"], "verified")
        client.refresh_from_db()
        self.assertEqual(client.status, "onboarding")
        self.assertEqual(self.act(self.omem, f"checklist/{b.pk}/not-applicable", {"reason": " "}).data["reason"], [services.MSG_REASON])
        self.act(self.omem, f"checklist/{b.pk}/not-applicable", {"reason": "Sole trader"})
        client.refresh_from_db()
        self.assertEqual((client.status, optional.status), ("active", "pending"))  # the optional item never blocked it
        self.assertIsNotNone(client.activated_at)
        self.assertTrue(Notification.objects.filter(user=self.ohead, kind="client_active").exists())
        self.assertIn("activated", self.actions(client))

    def test_resetting_a_required_item_returns_the_client_to_onboarding(self):
        client = self.mkclient()
        self.verified_all(client)
        client.refresh_from_db()
        self.assertEqual(client.status, "active")
        self.act(self.omem, f"checklist/{self.item(client).pk}/reset", {"note": "Expired"})
        client.refresh_from_db()
        self.assertEqual(client.status, "onboarding")

    def test_verify_rules(self):
        client = self.mkclient()
        item = self.item(client)
        self.assertEqual(self.act(self.omem, f"checklist/{item.pk}/verify").data["detail"], services.MSG_STATE)  # pending: nothing uploaded
        self.upload(self.omem, item)
        att = Attachment.objects.get(object_id=item.pk, category="kyc")
        att.archived_at = timezone.now()
        att.save()
        self.assertEqual(self.act(self.omem, f"checklist/{item.pk}/verify").data["detail"], services.MSG_NO_FILE)  # archived files do not count
        self.upload(self.omem, item)
        self.assertEqual(self.act(self.omem, f"checklist/{item.pk}/verify").status_code, 200)
        self.assertEqual(self.act(self.omem, f"checklist/{item.pk}/verify").status_code, 400)  # already verified
        self.assertEqual(self.act(self.omem, f"checklist/{item.pk}/reset").data["status"], "pending")
        self.assertEqual(self.act(self.omem, f"checklist/{item.pk}/reset").status_code, 400)

    def test_verifier_is_recorded(self):
        item = self.item(self.mkclient())
        self.upload(self.omem, item)
        self.assertEqual(self.act(self.omem2, f"checklist/{item.pk}/verify").data["verified_by_name"], self.omem2.full_name)

    def test_customising_a_clients_checklist_is_head_only(self):
        client = self.mkclient()
        url = f"clients/{client.pk}/checklist"
        self.assertEqual(self.act(self.omem, url, {"name_en": "Bank letter", "name_ar": "خطاب البنك"}).status_code, 403)
        self.assertEqual(self.act(self.ohead, url, {"name_en": "Bank letter", "name_ar": " "}).status_code, 400)
        res = self.act(self.ohead, url, {"name_en": "Bank letter", "name_ar": "خطاب البنك", "required": True})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["checklist"]), 4)
        new = client.checklist.get(name_en="Bank letter")
        self.assertEqual(self.act(self.omem, f"checklist/{new.pk}/required", {"required": False}).status_code, 403)
        self.assertFalse(self.act(self.ohead, f"checklist/{new.pk}/required", {"required": False}).data["required"])
        self.assertEqual(self.act(self.ohead, f"checklist/{new.pk}/archive").status_code, 200)
        self.assertEqual(len(self.client.get(f"/api/operations/clients/{client.pk}/").data["checklist"]), 3)  # archived, never deleted
        self.assertTrue(ChecklistItem.objects.filter(pk=new.pk).exists())
        self.assertEqual(self.act(self.ohead, f"checklist/{new.pk}/archive").status_code, 400)

    def test_adding_a_required_item_to_an_active_client_reopens_onboarding(self):
        client = self.mkclient()
        self.verified_all(client)
        self.act(self.ohead, f"clients/{client.pk}/checklist", {"name_en": "Bank letter", "name_ar": "خطاب البنك"})
        client.refresh_from_db()
        self.assertEqual(client.status, "onboarding")

    def test_database_needs_a_reason_for_not_applicable(self):
        item = self.item(self.mkclient())
        with self.assertRaises(IntegrityError), transaction.atomic():
            ChecklistItem.objects.filter(pk=item.pk).update(status="not_applicable", na_reason="")

    def test_legacy_clients_without_a_checklist_stay_as_they_are(self):
        legacy = self.mkclient(status="active", items=False)
        services.recompute_status(self.ohead, legacy)
        legacy.refresh_from_db()
        self.assertEqual(legacy.status, "active")


class RecurringTests(OCase):
    def test_due_dates_for_every_frequency(self):
        s = date(2026, 1, 31)
        mk = lambda f, n=None: RecurringTask(frequency=f, interval_days=n, start_date=s)
        self.assertEqual(services.due_date(mk("daily"), 3), date(2026, 2, 3))
        self.assertEqual(services.due_date(mk("weekly"), 2), date(2026, 2, 14))
        self.assertEqual(services.due_date(mk("biweekly"), 1), date(2026, 2, 14))
        self.assertEqual(services.due_date(mk("monthly"), 1), date(2026, 2, 28))  # clamped
        self.assertEqual(services.due_date(mk("monthly"), 2), date(2026, 3, 31))  # and does not drift
        self.assertEqual(services.due_date(mk("yearly"), 1), date(2027, 1, 31))
        self.assertEqual(services.due_date(RecurringTask(frequency="yearly", start_date=date(2024, 2, 29)), 1), date(2025, 2, 28))
        self.assertEqual(services.due_date(mk("custom", 10), 2), date(2026, 2, 20))

    def test_create_validation_and_head_only(self):
        c = self.mkclient()
        self.as_user(self.omem)
        self.assertEqual(self.client.post("/api/operations/recurring/", {"client": c.pk}, format="json").status_code, 403)
        today = timezone.localdate().isoformat()
        bad = [({"title": " "}, "title"), ({"frequency": "hourly"}, "frequency"), ({"frequency": "custom"}, "interval_days"), ({"frequency": "custom", "interval_days": 400}, "interval_days"),
               ({"frequency": "custom", "interval_days": 0}, "interval_days"), ({"start_date": "soon"}, "start_date"), ({"start_date": (timezone.localdate() - timedelta(days=1)).isoformat()}, "start_date"),
               ({"assignee": self.hr.pk}, "assignee")]
        for over, field in bad:
            self.assertIn(field, self.recurring(c, **over).data, over)
        self.assertEqual(self.recurring(c, frequency="custom", interval_days=45).status_code, 201)
        self.assertEqual(RecurringTask.objects.filter(client=c).count(), 1)

    @mock.patch("django.utils.timezone.localdate", return_value=date(2026, 6, 1))  # a fixed Monday: the dates below never land on a closed day
    def test_a_task_starting_today_appears_immediately_and_only_once(self, _today):
        c = self.mkclient()
        res = self.recurring(c)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(TaskInstance.objects.filter(client=c).count(), 1)
        self.assertEqual(services.generate_due(), 0)
        self.assertEqual(services.generate_due(), 0)
        t = TaskInstance.objects.get()
        self.assertEqual((t.assignee, t.status), (self.omem, "open"))
        self.assertTrue(Notification.objects.filter(user=self.omem, kind="task_due").exists())
        self.assertEqual(RecurringTask.objects.get().next_due, add_month(timezone.localdate()))

    @mock.patch("django.utils.timezone.localdate", return_value=date(2026, 6, 1))  # a fixed Monday: the dates below never land on a closed day
    def test_future_start_creates_nothing_until_due(self, _today):
        c = self.mkclient()
        later = timezone.localdate() + timedelta(days=10)
        self.recurring(c, start_date=later.isoformat(), frequency="weekly")
        self.assertEqual(TaskInstance.objects.count(), 0)
        self.assertEqual(services.generate_due(later - timedelta(days=1)), 0)
        self.assertEqual(services.generate_due(later), 1)
        self.assertEqual(services.generate_due(later), 0)
        self.assertEqual(services.generate_due(later + timedelta(days=14)), 2)  # catches up on both missed weeks, once each
        self.assertEqual(list(TaskInstance.objects.values_list("due_date", flat=True).order_by("due_date")), [later, later + timedelta(days=7), later + timedelta(days=14)])

    def test_long_gaps_do_not_flood_the_list(self):
        c = self.mkclient()
        self.recurring(c, frequency="daily")
        services.generate_due(timezone.localdate() + timedelta(days=400))
        self.assertLessEqual(TaskInstance.objects.count(), 13)
        self.assertGreater(RecurringTask.objects.get().next_due, timezone.localdate() + timedelta(days=400))

    def test_paused_tasks_generate_nothing_and_resume_from_today(self):
        c = self.mkclient()
        self.recurring(c, frequency="daily")
        task = RecurringTask.objects.get()
        self.as_user(self.ohead)
        self.assertFalse(self.client.patch(f"/api/operations/recurring/{task.pk}/", {"active": False}, format="json").data["active"])
        self.assertEqual(services.generate_due(timezone.localdate() + timedelta(days=5)), 0)
        self.assertEqual(self.client.patch(f"/api/operations/recurring/{task.pk}/", {"active": True, "frequency": "weekly"}, format="json").status_code, 200)
        task.refresh_from_db()
        self.assertGreaterEqual(task.next_due, timezone.localdate())

    def test_editing_is_head_only_and_validated(self):
        self.recurring()
        task = RecurringTask.objects.get()
        self.as_user(self.omem)
        self.assertEqual(self.client.patch(f"/api/operations/recurring/{task.pk}/", {"title": "x"}, format="json").status_code, 403)
        self.as_user(self.ohead)
        self.assertIn("title", self.client.patch(f"/api/operations/recurring/{task.pk}/", {"title": ""}, format="json").data)
        res = self.client.patch(f"/api/operations/recurring/{task.pk}/", {"title": "Quarterly VAT", "assignee": self.omem2.pk}, format="json")
        self.assertEqual((res.data["title"], res.data["assignee"]), ("Quarterly VAT", self.omem2.pk))

    def test_unassigned_tasks_notify_the_head(self):
        self.recurring(assignee=None)
        self.assertTrue(Notification.objects.filter(user=self.ohead, kind="task_due").exists())

    def test_database_blocks_two_instances_for_one_date(self):
        self.recurring()
        t = TaskInstance.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            TaskInstance.objects.create(recurring=t.recurring, client=t.client, title="x", due_date=t.due_date)

    def test_management_command_is_idempotent(self):
        c = self.mkclient()
        self.recurring(c, frequency="daily", start_date=timezone.localdate().isoformat())
        before = TaskInstance.objects.count()
        call_command("generate_recurring_tasks")
        call_command("generate_recurring_tasks")
        self.assertEqual(TaskInstance.objects.count(), before)


def add_month(d):
    return services.due_date(RecurringTask(frequency="monthly", start_date=d), 1)


class TaskTests(OCase):
    def task(self, assignee=None, due=0):
        c = self.mkclient()
        r = RecurringTask.objects.create(client=c, title="Reconcile", frequency="daily", start_date=timezone.localdate(), next_due=timezone.localdate() + timedelta(days=30), created_by=self.ohead)
        return TaskInstance.objects.create(recurring=r, client=c, title="Reconcile", due_date=timezone.localdate() + timedelta(days=due), assignee=assignee)

    def test_complete_by_the_head_with_note(self):
        # Since objective 21 a member submits for review; closing a task straight away is the head's shortcut.
        t = self.task(self.omem)
        self.assertEqual(self.act(self.omem, f"tasks/{t.pk}/complete", {"note": "All matched"}).status_code, 403)
        res = self.act(self.ohead, f"tasks/{t.pk}/complete", {"note": "All matched"})
        self.assertEqual((res.status_code, res.data["status"], res.data["completion_note"], res.data["closed_by_name"]), (200, "done", "All matched", self.ohead.full_name))
        self.assertEqual(self.act(self.ohead, f"tasks/{t.pk}/complete").data["detail"], services.MSG_TASK_CLOSED)
        self.assertEqual(self.act(self.omem, f"tasks/{t.pk}/skip", {"reason": "x"}).status_code, 400)
        self.assertIn("task_completed", self.actions(t.client))

    def test_note_is_optional_but_bounded(self):
        t = self.task(self.omem)
        self.assertIn("note", self.act(self.ohead, f"tasks/{t.pk}/complete", {"note": "x" * 1001}).data)
        self.assertEqual(self.act(self.ohead, f"tasks/{t.pk}/complete").status_code, 200)

    def test_skip_needs_a_reason(self):
        t = self.task(self.omem)
        self.assertEqual(self.act(self.omem, f"tasks/{t.pk}/skip", {"reason": " "}).data["reason"], [services.MSG_SKIP])
        res = self.act(self.omem, f"tasks/{t.pk}/skip", {"reason": "Client on holiday"})
        self.assertEqual((res.data["status"], res.data["skip_reason"]), ("skipped", "Client on holiday"))

    def test_only_the_assignee_or_the_head(self):
        t = self.task(self.omem)
        self.assertEqual(self.act(self.omem2, f"tasks/{t.pk}/complete").status_code, 403)
        for key in ("ceo", "commercial_head", "commercial_member", "hr_head", "marketing"):
            self.assertIn(self.act(self.users[key], f"tasks/{t.pk}/complete").status_code, (403, 404), key)
        self.assertEqual(self.act(self.ohead, f"tasks/{t.pk}/complete").status_code, 200)

    def test_filters(self):
        mine, other, late = self.task(self.omem), self.task(self.omem2), self.task(self.omem, due=-3)
        self.as_user(self.omem)
        ids = lambda q: {r["id"] for r in self.client.get(f"/api/operations/tasks/{q}").data["results"]}
        self.assertEqual(ids("?mine=1"), {mine.pk, late.pk})
        self.assertEqual(ids("?overdue=1"), {late.pk})
        self.assertEqual(ids(f"?client={other.client_id}"), {other.pk})
        self.assertEqual(ids("?status=open"), {mine.pk, other.pk, late.pk})
        row = next(r for r in self.client.get("/api/operations/tasks/?overdue=1").data["results"])
        self.assertTrue(row["overdue"] and row["can_work"])

    def test_commercial_can_read_tasks_of_their_clients_only(self):
        t = self.task(self.omem)
        t.client.contracts.create(ref="CT-9", lead=Lead.objects.create(ref="LD-9", company_name="X", phone="0770000099", created_by=self.mkt, status="qualified", assigned_to=self.cmem), requested_by=self.cmem, status="handed_over")
        self.as_user(self.cmem)
        self.assertEqual(self.client.get("/api/operations/tasks/").data["count"], 1)
        self.assertEqual(self.client.post(f"/api/operations/tasks/{t.pk}/complete/", {}, format="json").status_code, 403)
        self.as_user(self.make_user("c3@x.com", "Commercial", "member"))
        self.assertEqual(self.client.get("/api/operations/tasks/").data["count"], 0)

    def test_my_work_and_reminders(self):
        mine, theirs, future = self.task(self.omem, due=-1), self.task(self.omem2), self.task(self.omem, due=5)
        unassigned = self.task(None)
        item = self.make_item_uploaded()

        def kinds(user):
            self.as_user(user)
            return sorted(i["kind"] for i in self.client.get("/api/my-work/").data["items"] if i["kind"].startswith("op_"))

        self.assertEqual(kinds(self.omem), ["op_task", "op_verify"])  # members verify documents too
        self.assertEqual(kinds(self.omem2), ["op_task", "op_verify"])
        self.assertEqual(kinds(self.ohead), ["op_task", "op_verify"])
        self.assertEqual(kinds(self.chead), [])
        # The first My Work request of the day already ran the daily job, so the reminder exists and cannot repeat.
        self.assertEqual(Notification.objects.filter(user=self.omem, kind="overdue").count(), 1)
        self.assertEqual(reminders.overdue_tasks(), 0)  # once per task per date

    def make_item_uploaded(self):
        item = self.item(self.mkclient())
        self.upload(self.omem, item)
        return item


class MeetingTests(OCase):
    def log(self, user, client, **over):
        body = {"client": client.pk, "held_on": timezone.localdate().isoformat(), "notes": "Reviewed the books"}
        body.update(over)
        self.as_user(user)
        return self.client.post("/api/operations/meetings/", body, format="json")

    def test_log_suggests_the_next_date_from_the_cadence(self):
        c = self.mkclient(status="active")
        res = self.log(self.omem, c)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["next_date"], (timezone.localdate() + timedelta(days=30)).isoformat())
        self.assertEqual(self.log(self.omem, c, next_date=(timezone.localdate() + timedelta(days=10)).isoformat()).data["next_date"], (timezone.localdate() + timedelta(days=10)).isoformat())
        self.assertIn("qa_meeting_logged", self.actions(c))

    def test_validation(self):
        c = self.mkclient(status="active")
        today = timezone.localdate()
        for over, field in [({"held_on": ""}, "held_on"), ({"held_on": "x"}, "held_on"), ({"held_on": (today + timedelta(days=1)).isoformat()}, "held_on"),
                            ({"notes": " "}, "notes"), ({"next_date": today.isoformat()}, "next_date"), ({"next_date": "later"}, "next_date")]:
            self.assertIn(field, self.log(self.omem, c, **over).data, over)
        self.assertEqual(QAMeeting.objects.count(), 0)

    def test_commercial_is_read_only(self):
        c = self.mkclient(owner=self.cmem, status="active")
        self.assertEqual(self.log(self.cmem, c).status_code, 403)
        self.assertEqual(self.log(self.chead, c).status_code, 403)
        self.log(self.omem, c)
        self.as_user(self.cmem)
        self.assertEqual(self.client.get(f"/api/operations/meetings/?client={c.pk}").data["count"], 1)
        self.as_user(self.make_user("c4@x.com", "Commercial", "member"))
        self.assertEqual(self.client.get(f"/api/operations/meetings/?client={c.pk}").data["count"], 0)
        self.assertEqual(self.log(self.users["hr_head"], c).status_code, 403)

    def test_cadence(self):
        c = self.mkclient(status="active")
        for bad in (6, 400, "x", None):
            self.assertIn("qa_cadence_days", self.act(self.ohead, f"clients/{c.pk}/cadence", {"qa_cadence_days": bad}).data, bad)
        self.assertEqual(self.act(self.ohead, f"clients/{c.pk}/cadence", {"qa_cadence_days": 14}).data["qa_cadence_days"], 14)

    def test_next_due_and_overdue_flag(self):
        c = self.mkclient(status="active")
        today = timezone.localdate()
        QAMeeting.objects.create(client=c, held_on=today - timedelta(days=40), notes="x", next_date=today - timedelta(days=5), logged_by=self.omem)
        self.as_user(self.omem)
        row = self.client.get("/api/operations/clients/").data["results"][0]
        self.assertEqual((str(row["next_qa_due"]), row["qa_overdue"]), ((today - timedelta(days=5)).isoformat(), True))
        self.log(self.omem, c)
        row = self.client.get("/api/operations/clients/").data["results"][0]
        self.assertFalse(row["qa_overdue"])

    def test_overdue_meeting_reminder_once(self):
        c = self.mkclient(status="active")
        QAMeeting.objects.create(client=c, held_on=timezone.localdate() - timedelta(days=60), notes="x", next_date=timezone.localdate() - timedelta(days=2), logged_by=self.omem)
        self.assertEqual(reminders.overdue_meetings(), 1)
        self.assertEqual(reminders.overdue_meetings(), 0)
        self.assertTrue(Notification.objects.filter(user=self.ohead, kind="qa_overdue").exists())

    def test_list_counts_and_cost(self):
        def cost():
            self.as_user(self.ohead)
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get("/api/operations/clients/?page_size=100").status_code, 200)
            return len(ctx)

        self.mkclient()
        few = cost()
        for _ in range(6):
            c = self.mkclient()
            RecurringTask.objects.create(client=c, title="t", frequency="daily", start_date=timezone.localdate(), next_due=timezone.localdate(), created_by=self.ohead)
        self.assertEqual(cost(), few)
        row = self.client.get("/api/operations/clients/").data["results"][0]
        self.assertEqual((row["required_total"], row["required_done"]), (2, 0))

    def test_daily_job_runs_everything(self):
        c = self.mkclient(status="active")
        self.recurring(c, frequency="daily")
        self.assertEqual(reminders.run(), 0)


class AssigneeTests(OCase):
    def test_lists_active_operation_people_for_anyone_with_access(self):
        self.as_role("commercial_member")
        names = {p["full_name"] for p in self.client.get("/api/operations/assignees/").data}
        self.assertEqual(names, {self.ohead.full_name, self.omem.full_name, self.omem2.full_name})
        self.assert_matrix("get", "/api/operations/assignees/", {"ceo": 200, "commercial_head": 200, "commercial_member": 200, "operation_head": 200, "operation_member": 200, "*": 403})
