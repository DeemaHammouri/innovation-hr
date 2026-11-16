"""Objective 21: task lifecycle, review, escalation, deliverables to the portal, monitoring, and identical report numbers."""
import csv
import io
from datetime import date, timedelta

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from audit.models import AuditEntry
from core.access import content_type_for
from files.models import Attachment
from notifications.models import Notification
from operations import lifecycle, reminders
from operations.models import Deliverable, Escalation, RecurringTask, TaskInstance
from operations.tests import OCase, PDF


class LCase(OCase):
    def task(self, assignee=None, due=None, client=None):
        client = client or self.mkclient()
        rule = RecurringTask.objects.create(client=client, title="Monthly VAT", frequency="monthly", start_date=date(2026, 1, 1), next_due=date(2026, 1, 1), created_by=self.ohead)
        n = TaskInstance.objects.count() + 1
        return TaskInstance.objects.create(recurring=rule, client=client, title=f"VAT {n}", due_date=due or timezone.localdate() + timedelta(days=5), assignee=assignee or self.omem, rule_version=n, period=date(2026, 1, 1) + timedelta(days=n))

    def do(self, user, task, action, body=None):
        self.as_user(user)
        return self.client.post(f"/api/operations/tasks/{task.pk}/{action}/", body or {}, format="json")

    def status(self, task):
        task.refresh_from_db()
        return task.status

    def actions(self, client):
        return list(AuditEntry.objects.filter(content_type=content_type_for(type(client)), object_id=client.pk).order_by("id").values_list("action", flat=True))


class LifecycleTests(LCase):
    def test_the_usual_road_with_every_step_logged(self):
        t = self.task()
        steps = [("start", {}, "in_progress"), ("progress", {"progress": 40, "note": "Half way"}, "in_progress"), ("wait", {"reason": "Waiting for the invoices"}, "waiting"),
                 ("resume", {}, "in_progress"), ("block", {"reason": "No access to the portal"}, "blocked"), ("resume", {}, "in_progress"),
                 ("submit", {"note": "Filed"}, "submitted")]
        for action, body, want in steps:
            res = self.do(self.omem, t, action, body)
            self.assertEqual(res.status_code, 200, (action, res.data))
            self.assertEqual(res.data["status"], want, action)
        self.assertEqual(self.do(self.ohead, t, "approve").data["status"], "done")
        got = self.actions(t.client)
        for a in ("task_started", "task_progress", "task_waiting", "task_resumed", "task_blocked", "task_submitted", "task_approved"):
            self.assertIn(a, got)

    def test_waiting_and_blocked_need_a_reason_and_progress_is_a_number_up_to_100(self):
        t = self.task()
        self.do(self.omem, t, "start")
        for action in ("wait", "block"):
            res = self.do(self.omem, t, action, {"reason": "  "})
            self.assertEqual((res.status_code, "reason" in res.data), (400, True), action)
        for bad in (-1, 101, "x", None):
            self.assertEqual(self.do(self.omem, t, "progress", {"progress": bad}).status_code, 400, bad)
        self.assertEqual(self.status(t), "in_progress")

    def test_illegal_steps_are_refused(self):
        t = self.task()
        for action, body in (("progress", {"progress": 10}), ("wait", {"reason": "x"}), ("submit", {}), ("resume", {})):
            self.assertEqual(self.do(self.omem, t, action, body).status_code, 400, action)  # not started yet
        self.assertEqual(self.do(self.omem, t, "approve").status_code, 403)
        self.do(self.omem, t, "start")
        self.assertEqual(self.do(self.omem, t, "start").status_code, 400)
        self.assertEqual(self.do(self.ohead, t, "approve").status_code, 400)  # not submitted

    def test_only_the_assignee_or_the_head_works_a_task(self):
        t = self.task()
        self.assertEqual(self.do(self.omem2, t, "start").status_code, 403)
        self.assertEqual(self.do(self.cmem, t, "start").status_code, 404)  # a deal that is not theirs is not even visible
        self.assertEqual(self.do(self.ohead, t, "start").status_code, 200)

    def test_the_manager_sends_it_back_with_a_note_and_the_assignee_resubmits(self):
        t = self.task()
        self.do(self.omem, t, "start")
        self.do(self.omem, t, "submit")
        self.assertEqual(self.do(self.ohead, t, "return", {"comment": " "}).status_code, 400)
        res = self.do(self.ohead, t, "return", {"comment": "Attach the receipt"})
        self.assertEqual((res.status_code, res.data["status"], res.data["review_note"]), (200, "in_progress", "Attach the receipt"))
        self.assertTrue(Notification.objects.filter(user=self.omem, kind="task_returned").exists())
        self.assertEqual(self.do(self.omem, t, "submit").data["status"], "submitted")

    def test_nobody_reviews_their_own_work_and_members_cannot_review(self):
        t = self.task(assignee=self.ohead)
        self.do(self.ohead, t, "start")
        self.do(self.ohead, t, "submit")
        self.assertEqual(self.do(self.ohead, t, "approve").status_code, 403)
        self.assertEqual(self.do(self.omem, t, "approve").status_code, 403)
        self.assertEqual(self.do(self.ceo, t, "approve").status_code, 200)  # the CEO reviews the head's own task

    def test_members_cannot_close_a_task_without_review(self):
        t = self.task()
        self.assertEqual(self.do(self.omem, t, "complete", {"note": "x"}).status_code, 403)
        self.assertEqual(self.do(self.ohead, t, "complete", {"note": "done"}).status_code, 200)

    def test_notes_and_files_on_a_task(self):
        t = self.task()
        self.as_user(self.omem)
        res = self.client.post("/api/comments/", {"target": f"task:{t.pk}", "body": "Called the client"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        up = self.client.post(f"/api/files/?target=task:{t.pk}", {"file": SimpleUploadedFile("vat.pdf", PDF, content_type="application/pdf"), "category": "other"}, format="multipart")
        self.assertEqual(up.status_code, 201, up.data)
        self.as_user(self.omem2)
        self.assertEqual(self.client.post(f"/api/files/?target=task:{t.pk}", {"file": SimpleUploadedFile("x.pdf", PDF, content_type="application/pdf"), "category": "other"}, format="multipart").status_code, 403)


class EscalationTests(LCase):
    def test_a_task_is_escalated_once_per_level_and_the_database_agrees(self):
        t = self.task()
        self.assertEqual(self.do(self.omem, t, "escalate", {"reason": " "}).status_code, 400)
        res = self.do(self.omem, t, "escalate", {"reason": "Client does not answer"})
        self.assertEqual((res.status_code, res.data["escalation_level"]), (200, 1))
        self.assertTrue(Notification.objects.filter(user=self.ohead, kind="task_escalated").exists())
        self.assertEqual(self.do(self.omem, t, "escalate", {"reason": "Still nothing"}).status_code, 403)  # level 2 is the head's call
        res = self.do(self.ohead, t, "escalate", {"reason": "Needs the CEO"})
        self.assertEqual((res.status_code, res.data["escalation_level"]), (200, 2))
        self.assertTrue(Notification.objects.filter(user=self.ceo, kind="task_escalated").exists())
        self.assertEqual(self.do(self.ohead, t, "escalate", {"reason": "Again"}).status_code, 400)
        self.assertEqual(list(Escalation.objects.filter(task=t).values_list("level", flat=True)), [1, 2])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Escalation.objects.create(task=t, level=1, reason="duplicate")

    def test_overdue_tasks_are_escalated_by_the_system_one_level_per_run_and_repeats_change_nothing(self):
        today = timezone.localdate()
        t = self.task(due=today - timedelta(days=6))
        young = self.task(due=today - timedelta(days=1))
        self.assertEqual(reminders.escalate_overdue(today), 1)
        self.assertEqual(reminders.escalate_overdue(today), 1)  # the second level, a run later
        self.assertEqual(reminders.escalate_overdue(today), 0)
        self.assertEqual(reminders.escalate_overdue(today), 0)
        self.assertEqual(list(Escalation.objects.filter(task=t).values_list("level", "by_id")), [(1, None), (2, None)])
        self.assertFalse(Escalation.objects.filter(task=young).exists())

    def test_a_closed_task_is_never_escalated(self):
        t = self.task(due=timezone.localdate() - timedelta(days=9))
        TaskInstance.objects.filter(pk=t.pk).update(status="done")
        self.assertEqual(reminders.escalate_overdue(), 0)


class DeliverableTests(LCase):
    def setUp(self):
        super().setUp()
        from accounts.models import Role, User

        self.mine = self.mkclient()
        self.portal = User.objects.create_user(email="portal@x.com", password="Demo-12345x", full_name="Portal", role_ref=Role.objects.get(key="client"))

    def link_portal(self):
        type(self.mine).objects.filter(pk=self.mine.pk).update(portal_user=self.portal)

    def attach(self, task, name="vat-return.pdf"):
        return Attachment.objects.create(
            file=ContentFile(PDF, name=name), original_name=name, content_type_header="application/pdf", size=len(PDF), category="other",
            uploaded_by=self.omem, content_type=content_type_for(TaskInstance), object_id=task.pk,
        )

    def submitted(self, client=None):
        t = self.task(client=client or self.mine)
        self.do(self.omem, t, "start")
        self.do(self.omem, t, "submit")
        return t

    def test_publishing_needs_a_submitted_task_a_file_on_that_task_and_a_portal_account(self):
        t = self.task(client=self.mine)
        att = self.attach(t)
        self.assertEqual(self.do(self.omem, t, "publish", {"attachment": att.pk, "title": "VAT return"}).status_code, 400)  # not submitted yet
        self.do(self.omem, t, "start")
        self.do(self.omem, t, "submit")
        self.assertEqual(self.do(self.omem, t, "publish", {"attachment": att.pk, "title": "VAT return"}).status_code, 400)  # no portal account
        self.assertFalse(Deliverable.objects.exists())

    def test_the_task_list_tells_the_assignee_and_the_reviewer_when_a_file_can_be_shown(self):
        self.link_portal()
        t = self.task(client=self.mine)
        def flag(user):
            self.as_user(user)
            return self.client.get(f"/api/operations/tasks/{t.pk}/").data["can_publish"]

        self.assertFalse(flag(self.omem))  # not submitted yet
        self.do(self.omem, t, "start")
        self.do(self.omem, t, "submit")
        self.assertTrue(flag(self.omem))  # the assignee can no longer "work" the task but may still show the file
        self.assertTrue(flag(self.ohead))

    def test_the_client_sees_only_their_own_files_and_acknowledges_once(self):
        self.link_portal()
        t = self.submitted()
        other = self.mkclient()
        other_task = self.task(client=other)
        att, other_att = self.attach(t), self.attach(other_task, "other.pdf")
        self.assertEqual(self.do(self.omem, t, "publish", {"attachment": att.pk, "title": "VAT return"}).status_code, 200)
        self.assertEqual(self.do(self.omem, t, "publish", {"attachment": att.pk, "title": "Again"}).status_code, 400)  # once per file
        self.assertEqual(self.do(self.omem, t, "publish", {"attachment": other_att.pk, "title": "Not mine"}).status_code, 400)  # another task's file
        d = Deliverable.objects.get()
        self.assertTrue(Notification.objects.filter(user=self.portal, kind="deliverable_published").exists())
        # a second client with its own file: the first client never sees it
        from accounts.models import Role, User

        portal2 = User.objects.create_user(email="portal2@x.com", password="Demo-12345x", full_name="Portal Two", role_ref=Role.objects.get(key="client"))
        type(other).objects.filter(pk=other.pk).update(portal_user=portal2)
        self.assertEqual(self.do(self.omem, other_task, "start").status_code, 200)
        self.do(self.omem, other_task, "submit")
        self.do(self.omem, other_task, "publish", {"attachment": other_att.pk, "title": "Theirs"})
        self.as_user(self.portal)
        self.assertEqual([r["title"] for r in self.client.get("/api/portal/deliverables/").data], ["VAT return"])
        theirs = Deliverable.objects.get(title="Theirs")
        self.assertEqual(self.client.get(f"/api/portal/deliverables/{theirs.pk}/download/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/portal/deliverables/{theirs.pk}/acknowledge/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/portal/deliverables/{d.pk}/download/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/portal/deliverables/{d.pk}/acknowledge/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/portal/deliverables/{d.pk}/acknowledge/").status_code, 400)  # once
        d.refresh_from_db()
        self.assertEqual(d.acknowledged_by_id, self.portal.pk)
        self.assertIn("deliverable_acknowledged", self.actions(self.mine))
        self.as_user(self.omem)  # Operation staff are not the client: the portal endpoints are closed to them
        self.assertEqual(self.client.get("/api/portal/deliverables/").status_code, 403)


class MonitoringTests(LCase):
    def test_the_head_and_the_ceo_see_the_numbers_nobody_else_does(self):
        today = timezone.localdate()
        late = self.task(due=today - timedelta(days=3))
        blocked = self.task()
        self.do(self.omem, blocked, "start")
        self.do(self.omem, blocked, "block", {"reason": "No access"})
        self.assert_matrix("get", "/api/operations/monitoring/", {"ceo": 200, "operation_head": 200, "*": 403})
        self.as_user(self.ohead)
        data = self.client.get("/api/operations/monitoring/").data
        self.assertEqual((data["totals"]["overdue"], data["totals"]["blocked"]), (1, 1))
        person = next(p for p in data["people"] if p["id"] == self.omem.pk)
        self.assertEqual((person["blocked"], person["overdue"]), (1, 1))
        self.assertIn(late.pk, [a["id"] for a in data["attention"]])
        self.assertNotIn("price", str(data).lower())
