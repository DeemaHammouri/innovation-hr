"""Objective 19: versioned KYC records with expiry, onboarding only when verified, one primary employee per project."""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from clients.models import Client
from notifications.models import Notification
from operations import services
from operations.models import ChecklistItem, Project, ProjectStaff
from operations.tests import OCase
from operations.tests_handover import HCase


class KycVersionTests(OCase):
    def verify(self, item, expires=None):
        body = {"expires_on": expires} if expires else {}
        return self.act(self.omem, f"checklist/{item.pk}/verify", body)

    def test_each_upload_is_a_new_version_and_old_ones_are_kept(self):
        c = self.mkclient()
        item = self.item(c)
        self.upload(self.omem, item, "a.pdf")
        self.assertEqual(self.verify(item).status_code, 200)
        self.upload(self.omem, item, "b.pdf")
        item.refresh_from_db()
        states = list(item.versions.order_by("number").values_list("number", "state", "filename"))
        self.assertEqual(states, [(1, "superseded", "a.pdf"), (2, "uploaded", "b.pdf")])
        self.assertEqual(item.status, "uploaded")  # the new document has not been checked
        self.as_user(self.omem)
        data = self.client.get(f"/api/operations/clients/{c.pk}/").data
        self.assertEqual(len(data["checklist"][0]["versions"]), 2)

    def test_replacing_a_verified_document_sends_an_active_client_back_to_onboarding(self):
        c = self.mkclient()
        self.verified_all(c)
        c.refresh_from_db()
        self.assertEqual(c.status, "active")
        self.upload(self.omem, self.item(c), "new.pdf")
        c.refresh_from_db()
        self.assertEqual(c.status, "onboarding")

    def test_expiry_date_is_required_when_the_item_expires(self):
        c = self.mkclient()
        item = self.item(c)
        ChecklistItem.objects.filter(pk=item.pk).update(expires_required=True)
        self.upload(self.omem, item)
        self.assertEqual(self.verify(item).status_code, 400)
        self.assertEqual(self.verify(item, (timezone.localdate() - timedelta(days=1)).isoformat()).status_code, 400)
        day = (timezone.localdate() + timedelta(days=90)).isoformat()
        res = self.verify(item, day)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["expires_on"], day)

    def test_expired_document_returns_the_client_to_onboarding_and_is_idempotent(self):
        c = self.mkclient()
        self.verified_all(c)
        item = c.checklist.filter(required=True).first()
        ChecklistItem.objects.filter(pk=item.pk).update(expires_on=timezone.localdate() - timedelta(days=1))
        self.assertGreater(services.expire_documents(), 0)
        item.refresh_from_db()
        c.refresh_from_db()
        self.assertEqual((item.status, c.status), ("expired", "onboarding"))
        self.assertEqual(services.expire_documents(), 0)  # a second run changes and sends nothing
        self.assertIn("checklist_expired", self.actions(c))

    def test_a_new_upload_after_expiry_goes_back_to_uploaded(self):
        c = self.mkclient()
        item = self.item(c)
        self.upload(self.omem, item)
        self.verify(item)
        ChecklistItem.objects.filter(pk=item.pk).update(status="expired")
        self.upload(self.omem, item, "renewed.pdf")
        item.refresh_from_db()
        self.assertEqual(item.status, "uploaded")


class OnboardingNeedsVerifiedTests(OCase):
    def test_client_is_not_activated_while_a_required_item_is_unverified(self):
        c = self.mkclient()
        required = list(c.checklist.filter(required=True))
        for item in required[:-1]:
            self.upload(self.omem, item)
            self.act(self.omem, f"checklist/{item.pk}/verify")
        self.upload(self.omem, required[-1])  # uploaded but not verified
        c.refresh_from_db()
        self.assertEqual(c.status, "onboarding")
        self.act(self.omem, f"checklist/{required[-1].pk}/verify")
        c.refresh_from_db()
        self.assertEqual(c.status, "active")

    def test_an_expired_but_unmarked_document_does_not_count(self):
        c = self.mkclient()
        self.verified_all(c)
        item = c.checklist.filter(required=True).first()
        ChecklistItem.objects.filter(pk=item.pk).update(expires_on=timezone.localdate() - timedelta(days=1))
        services.recompute_status(self.ohead, Client.objects.get(pk=c.pk))
        c.refresh_from_db()
        self.assertEqual(c.status, "onboarding")


class StaffingTests(HCase):
    def project(self):
        h = self.submitted()
        res = self.call(self.ohead, h, "accept")
        self.assertEqual(res.status_code, 200, res.data)
        return Project.objects.get(handover_id=h.pk)

    def post(self, user, project, action, body):
        self.as_user(user)
        return self.client.post(f"/api/projects/{project.pk}/{action}/", body, format="json")

    def test_first_primary_needs_no_reason_and_replacing_needs_one(self):
        p = self.project()
        self.assertEqual(self.post(self.ohead, p, "primary", {"user": self.omem.pk}).status_code, 200)
        res = self.post(self.ohead, p, "primary", {"user": self.omem2.pk})
        self.assertEqual(res.status_code, 400)
        self.assertIn("reason", res.data)
        res = self.post(self.ohead, p, "primary", {"user": self.omem2.pk, "reason": "On leave"})
        self.assertEqual(res.status_code, 200, res.data)
        rows = list(ProjectStaff.objects.filter(project=p).order_by("id").values_list("user_id", "role", "end_reason"))
        self.assertEqual(rows, [(self.omem.pk, "primary", "On leave"), (self.omem2.pk, "primary", "")])
        self.assertEqual(ProjectStaff.objects.filter(project=p, role="primary", ended_at__isnull=True).count(), 1)

    def test_the_database_refuses_a_second_active_primary(self):
        p = self.project()
        ProjectStaff.objects.create(project=p, user=self.omem, role="primary", assigned_by=self.ohead)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProjectStaff.objects.create(project=p, user=self.omem2, role="primary", assigned_by=self.ohead)

    def test_support_people_are_unlimited_but_only_once_each(self):
        p = self.project()
        self.post(self.ohead, p, "primary", {"user": self.omem.pk})
        self.assertEqual(self.post(self.ohead, p, "support", {"user": self.omem2.pk}).status_code, 200)
        self.assertEqual(self.post(self.ohead, p, "support", {"user": self.omem2.pk}).status_code, 400)
        self.assertEqual(self.post(self.ohead, p, "remove", {"user": self.omem2.pk, "reason": "Finished"}).status_code, 200)
        self.assertEqual(self.post(self.ohead, p, "remove", {"user": self.omem.pk}).status_code, 400)  # the primary is replaced, not removed
        self.assertEqual(ProjectStaff.objects.filter(project=p).count(), 2)  # nothing deleted

    def test_only_operation_people_and_only_the_head_can_staff(self):
        p = self.project()
        self.assertEqual(self.post(self.ohead, p, "primary", {"user": self.cmem.pk}).status_code, 400)
        for user in (self.omem, self.cmem, self.hr):
            self.assertEqual(self.post(user, p, "primary", {"user": self.omem.pk}).status_code, 403, user.email)

    def test_staff_shows_on_the_project_and_the_person_is_told(self):
        p = self.project()
        self.post(self.ohead, p, "primary", {"user": self.omem.pk})
        self.as_user(self.ohead)
        row = self.client.get("/api/projects/").data["results"][0]
        self.assertEqual([s["name"] for s in row["staff"]], [self.omem.full_name])
        self.assertTrue(row["can_staff"])
        self.assertTrue(Notification.objects.filter(user=self.omem, kind="project_assigned").exists())
