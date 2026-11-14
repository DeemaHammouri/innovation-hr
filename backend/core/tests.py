from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from audit.models import AuditEntry, ImmutableError, record
from clients.models import Client
from comments.models import Comment
from core import mywork
from core.models import Sequence
from core.roles import ALL_ROLES, role_key
from core.testing import RoleCase
from files.models import Attachment
from lookups.models import ChecklistTemplateItem, RejectionReason, Service, SlaSetting, WorkHours
from notifications.messages import render
from notifications.models import Notification
from notifications.service import notify

PDF = b"%PDF-1.4\n%test\n"


class RoleKeyTests(RoleCase):
    def test_every_seat_maps_to_its_role(self):
        for key in ALL_ROLES:
            self.assertEqual(role_key(self.users[key]), key)

    def test_superuser_without_department_has_no_role(self):
        from accounts.models import User

        su = User.objects.create_superuser("dev@x.com", "pw-123456", full_name="Dev")
        self.assertIsNone(role_key(su))

    def test_me_endpoint_exposes_role_key(self):
        for key in ALL_ROLES:
            self.as_role(key)
            self.assertEqual(self.client.get("/api/auth/me/").data["role_key"], key)


class SequenceTests(TestCase):
    def test_readable_refs_count_up_per_prefix(self):
        self.assertEqual(Sequence.next_ref("LD"), "LD-0001")
        self.assertEqual(Sequence.next_ref("LD"), "LD-0002")
        self.assertEqual(Sequence.next_ref("QT"), "QT-0001")


class AuditTests(RoleCase):
    def setUp(self):
        super().setUp()
        self.c = Client.objects.create(company_name="Acme", created_by=self.users["ceo"])

    def test_entries_cannot_be_changed_or_deleted(self):
        e = record(self.users["ceo"], self.c, "created")
        e.comment = "edited"
        with self.assertRaises(ImmutableError):
            e.save()
        with self.assertRaises(ImmutableError):
            e.delete()
        with self.assertRaises(ImmutableError):
            AuditEntry.objects.all().delete()
        with self.assertRaises(ImmutableError):
            AuditEntry.objects.all().update(comment="x")

    def test_activity_endpoint_follows_the_record_permissions(self):
        record(self.users["ceo"], self.c, "created")
        self.assert_matrix("get", f"/api/activity/?target=client:{self.c.pk}", {"ceo": 200, "operation_head": 200, "operation_member": 200, "*": 404})  # Phase 5: Operation works on clients, Commercial reads

    def test_activity_has_no_write_endpoint(self):
        self.as_role("ceo")
        self.assertEqual(self.client.post(f"/api/activity/?target=client:{self.c.pk}", {}).status_code, 405)

    def test_unknown_or_bad_target_is_rejected(self):
        self.as_role("ceo")
        self.assertEqual(self.client.get("/api/activity/?target=client:9999").status_code, 404)
        self.assertEqual(self.client.get("/api/activity/?target=nonsense").status_code, 400)
        self.assertEqual(self.client.get("/api/activity/?target=ghost:1").status_code, 400)

    def test_client_create_and_edit_are_logged(self):
        self.as_role("operation_head")
        res = self.client.post("/api/clients/", {"company_name": "Beta Co"}, format="json")
        self.assertEqual(res.status_code, 201)
        cid = res.data["id"]
        self.client.patch(f"/api/clients/{cid}/", {"phone": "0790000000"}, format="json")
        actions = list(AuditEntry.objects.filter(object_id=cid).order_by("id").values_list("action", "to_value"))
        self.assertEqual(actions, [("created", ""), ("updated", "phone")])
        timeline = self.client.get(f"/api/activity/?target=client:{cid}").data["results"]
        self.assertEqual(timeline[0]["actor_name"], "Operation Head")


class NotificationTests(RoleCase):
    def test_text_is_stored_in_the_recipients_language(self):
        ar = self.users["hr_head"]
        ar.preferred_language = "ar"
        ar.save()
        notify(ar, "assigned", link="/x", actor="Sam", ref="LD-0001", name="Acme")
        notify(self.users["ceo"], "assigned", link="/x", actor="Sam", ref="LD-0001", name="Acme")
        self.assertEqual(Notification.objects.get(user=ar).title, "قام Sam بإسنادك إلى LD-0001")
        self.assertEqual(Notification.objects.get(user=self.users["ceo"]).title, "Sam assigned you LD-0001")

    def test_every_kind_exists_in_both_languages(self):
        from notifications.messages import CATALOG

        for kind, langs in CATALOG.items():
            self.assertEqual(set(langs), {"en", "ar"}, kind)
            self.assertNotEqual(render(kind, "ar", ref="R")[0], render(kind, "en", ref="R")[0])

    def test_dedupe_key_fires_once_and_inactive_users_are_skipped(self):
        u = self.users["ceo"]
        self.assertIsNotNone(notify(u, "overdue", dedupe_key="a", ref="R"))
        self.assertIsNone(notify(u, "overdue", dedupe_key="a", ref="R"))
        u2 = self.users["hr_head"]
        u2.is_active = False
        u2.save()
        self.assertIsNone(notify(u2, "overdue", ref="R"))

    def test_people_only_see_and_change_their_own(self):
        n = notify(self.users["ceo"], "signed", ref="CT-0001")
        self.as_role("hr_head")
        self.assertEqual(self.client.get("/api/notifications/").data["count"], 0)
        self.assertEqual(self.client.post(f"/api/notifications/{n.pk}/read/").status_code, 404)
        self.as_role("ceo")
        self.assertEqual(self.client.get("/api/notifications/unread-count/").data["count"], 1)
        self.assertEqual(self.client.post(f"/api/notifications/{n.pk}/read/").status_code, 204)
        self.assertEqual(self.client.get("/api/notifications/unread-count/").data["count"], 0)

    def test_mark_all_read(self):
        for _ in range(3):
            notify(self.users["ceo"], "signed", ref="CT-1")
        self.as_role("ceo")
        self.assertEqual(self.client.post("/api/notifications/read-all/").status_code, 204)
        self.assertEqual(self.client.get("/api/notifications/?unread=1").data["count"], 0)

    def test_requires_sign_in(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/notifications/").status_code, 401)


class CommentTests(RoleCase):
    def setUp(self):
        super().setUp()
        self.c = Client.objects.create(company_name="Acme", created_by=self.users["ceo"])
        self.url = f"/api/comments/?target=client:{self.c.pk}"

    def test_only_people_who_can_open_the_record_can_read_or_write(self):
        allowed = {"ceo": 200, "operation_head": 200, "operation_member": 200, "*": 404}
        self.assert_matrix("get", self.url, allowed)
        # Commercial can read a client but not comment (read-only); a Commercial member only sees clients of their own leads.
        self.assert_matrix("post", self.url, {"ceo": 201, "operation_head": 201, "operation_member": 201, "*": 404}, data={"body": "Hello"})

    def test_empty_comment_is_refused(self):
        self.as_role("ceo")
        res = self.client.post(self.url, {"body": "   "}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("body", res.data)

    def test_mention_is_limited_to_people_who_can_open_the_record(self):
        self.as_role("ceo")
        ok = self.client.post(self.url, {"body": "Please check", "mentions": [self.users["operation_head"].pk]}, format="json")
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(Notification.objects.filter(user=self.users["operation_head"], kind="mention").count(), 1)
        bad = self.client.post(self.url, {"body": "Secret", "mentions": [self.users["hr_member"].pk]}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(Comment.objects.count(), 1)
        self.assertFalse(Notification.objects.filter(user=self.users["hr_member"]).exists())

    def test_mentionable_lists_only_people_with_access_and_not_yourself(self):
        self.as_role("ceo")
        ids = {p["id"] for p in self.client.get(f"/api/mentionable/?target=client:{self.c.pk}").data}
        self.assertEqual(ids, {self.users[k].pk for k in ("operation_head", "operation_member")})

    def test_comment_is_recorded_in_the_activity_trail(self):
        self.as_role("ceo")
        self.client.post(self.url, {"body": "Noted"}, format="json")
        self.assertTrue(AuditEntry.objects.filter(object_id=self.c.pk, action="commented").exists())

    def test_comments_cannot_be_edited_or_deleted_through_the_api(self):
        self.as_role("ceo")
        cid = self.client.post(self.url, {"body": "Once"}, format="json").data["id"]
        self.assertEqual(self.client.delete(f"/api/comments/{cid}/").status_code, 404)
        self.assertEqual(self.client.patch(f"/api/comments/{cid}/", {"body": "x"}, format="json").status_code, 404)


class FileTests(RoleCase):
    def setUp(self):
        super().setUp()
        self.c = Client.objects.create(company_name="Acme", created_by=self.users["ceo"])
        self.url = f"/api/files/?target=client:{self.c.pk}"

    def upload(self, name="doc.pdf", content=PDF, role="operation_head", category=""):
        self.as_role(role)
        return self.client.post(self.url, {"file": SimpleUploadedFile(name, content), "category": category}, format="multipart")

    def test_upload_and_download_round_trip(self):
        res = self.upload()
        self.assertEqual(res.status_code, 201, res.data)
        att = Attachment.objects.get()
        self.assertNotIn("doc", att.file.name)  # stored under a random name, not the user's
        self.assertNotIn("url", res.data)
        dl = self.client.get(f"/api/files/{att.pk}/download/")
        self.assertEqual(dl.status_code, 200)
        self.assertEqual(b"".join(dl.streaming_content), PDF)
        self.assertEqual(dl["X-Content-Type-Options"], "nosniff")
        self.assertIn("attachment", dl["Content-Disposition"])

    def test_access_follows_the_parent_record(self):
        att_id = self.upload().data["id"]
        readers = {"ceo": 200, "operation_head": 200, "operation_member": 200, "*": 404}  # Phase 5: Operation works on clients; Commercial only for own deals
        self.assert_matrix("get", f"/api/files/{att_id}/download/", readers)
        self.assert_matrix("get", self.url, readers)

    def test_who_may_upload(self):
        for role, code in (("hr_head", 404), ("commercial_head", 404), ("operation_member", 201), ("ceo", 201)):
            self.assertEqual(self.upload(role=role).status_code, code, role)

    def test_type_allow_list_and_real_content_check(self):
        self.assertEqual(self.upload("run.exe", b"MZ\x90").status_code, 400)
        self.assertEqual(self.upload("page.html", b"<html>").status_code, 400)
        self.assertEqual(self.upload("fake.pdf", b"<script>alert(1)</script>").status_code, 400)
        self.assertEqual(self.upload("empty.pdf", b"").status_code, 400)
        self.assertEqual(self.upload("photo.PNG", b"\x89PNG\r\n\x1a\n....").status_code, 201)
        self.assertEqual(self.upload("sheet.xlsx", b"PK\x03\x04....").status_code, 201)

    def test_size_limit(self):
        big = PDF + b"0" * (10 * 1024 * 1024)
        self.assertEqual(self.upload("big.pdf", big).status_code, 400)

    def test_path_tricks_in_the_name_are_neutralised(self):
        res = self.upload("../../evil.pdf")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["original_name"], "evil.pdf")

    def test_archive_hides_the_file_and_is_recorded(self):
        att_id = self.upload().data["id"]
        res = self.client.post(f"/api/files/{att_id}/archive/", {"reason": "wrong file"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get(self.url).data["count"], 0)
        self.assertEqual(self.client.get(self.url + "&archived=1").data["count"], 1)
        self.assertTrue(Attachment.objects.filter(pk=att_id).exists())  # never hard-deleted
        self.assertTrue(AuditEntry.objects.filter(action="file_archived", comment="wrong file").exists())
        self.assertEqual(self.client.delete(f"/api/files/{att_id}/").status_code, 404)

    def test_requires_sign_in(self):
        att_id = self.upload().data["id"]
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(f"/api/files/{att_id}/download/").status_code, 401)


class LookupTests(RoleCase):
    def test_defaults_are_seeded_in_both_languages(self):
        self.assertGreaterEqual(RejectionReason.objects.count(), 5)
        self.assertTrue(Service.objects.exists() and ChecklistTemplateItem.objects.exists())
        for model in (RejectionReason, Service, ChecklistTemplateItem):
            for row in model.objects.all():
                self.assertTrue(row.name_en and row.name_ar)
        self.assertEqual(WorkHours.get().grace_minutes, 15)
        self.assertEqual(SlaSetting.get().follow_up_days, 3)

    def test_everyone_reads(self):
        for path in ("rejection-reasons/", "services/", "checklist-template/", "work-hours/", "sla/"):
            self.assert_matrix("get", f"/api/lookups/{path}", {"*": 200})

    def test_only_the_ceo_writes(self):
        body = {"name_en": "Too slow", "name_ar": "بطيء جداً"}
        self.assert_matrix("post", "/api/lookups/rejection-reasons/", {"ceo": 201, "*": 403}, data=body)
        self.assert_matrix("post", "/api/lookups/services/", {"ceo": 201, "*": 403}, data=body)
        self.assert_matrix("post", "/api/lookups/checklist-template/", {"ceo": 201, "*": 403}, data=body)
        self.assert_matrix("patch", "/api/lookups/work-hours/", {"ceo": 200, "*": 403}, data={"grace_minutes": 10})
        self.assert_matrix("patch", "/api/lookups/sla/", {"ceo": 200, "*": 403}, data={"follow_up_days": 2})

    def test_both_names_are_required_and_nothing_is_deleted(self):
        self.as_role("ceo")
        res = self.client.post("/api/lookups/rejection-reasons/", {"name_en": "Only English", "name_ar": " "}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("name_ar", res.data)
        rid = RejectionReason.objects.first().pk
        self.assertEqual(self.client.delete(f"/api/lookups/rejection-reasons/{rid}/").status_code, 405)
        self.client.patch(f"/api/lookups/rejection-reasons/{rid}/", {"is_active": False}, format="json")
        self.assertFalse(RejectionReason.objects.get(pk=rid).is_active)
        active = self.client.get("/api/lookups/rejection-reasons/?active=1").data
        self.assertNotIn(rid, [r["id"] for r in active])

    def test_duplicate_names_are_refused_but_editing_yourself_is_fine(self):
        self.as_role("ceo")
        body = {"name_en": "Too slow", "name_ar": "بطيء جداً"}
        first = self.client.post("/api/lookups/rejection-reasons/", body, format="json")
        self.assertEqual(first.status_code, 201)
        again = self.client.post("/api/lookups/rejection-reasons/", {"name_en": "too SLOW", "name_ar": "اسم آخر"}, format="json")
        self.assertEqual(again.status_code, 400)
        self.assertIn("name_en", again.data)
        same = self.client.patch(f"/api/lookups/rejection-reasons/{first.data['id']}/", {"name_en": "Too slow", "sort_order": 9}, format="json")
        self.assertEqual(same.status_code, 200)

    def test_blocked_while_password_change_is_pending(self):
        self.users["ceo"].must_change_password = True
        self.users["ceo"].save()
        self.as_role("ceo")
        self.assertEqual(self.client.get("/api/lookups/services/").status_code, 403)


class MyWorkTests(RoleCase):
    def test_endpoint_works_for_every_role_and_needs_sign_in(self):
        self.assert_matrix("get", "/api/my-work/", {"*": 200})
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/my-work/").status_code, 401)

    def test_items_come_from_providers_and_feed_the_badges(self):
        def fake(user):
            return [
                {"kind": "followup_due", "section": "pipeline", "ref": "LD-2", "title": "B", "link": "/x", "due": "2026-11-15", "overdue": False},
                {"kind": "followup_overdue", "section": "pipeline", "ref": "LD-1", "title": "A", "link": "/y", "due": "2026-11-10", "overdue": True},
            ] if user.role == "head" else []

        mywork._PROVIDERS.append(fake)
        try:
            self.as_role("commercial_head")
            data = self.client.get("/api/my-work/").data
            self.assertEqual([i["ref"] for i in data["items"]], ["LD-1", "LD-2"])  # overdue first
            self.assertEqual(data["badges"], {"pipeline": 2})
            self.assertEqual(data["role"], "commercial_head")
            self.as_role("commercial_member")
            self.assertEqual(self.client.get("/api/my-work/").data["items"], [])
        finally:
            mywork._PROVIDERS.remove(fake)

    def test_unread_notifications_count_is_included(self):
        notify(self.users["ceo"], "signed", ref="CT-1")
        self.as_role("ceo")
        self.assertEqual(self.client.get("/api/my-work/").data["unread_notifications"], 1)


class HarnessTests(RoleCase):
    def test_matrix_demands_every_role_to_be_covered(self):
        with self.assertRaises(AssertionError):
            self.assert_matrix("get", "/api/my-work/", {"ceo": 200})

    def test_matrix_fails_on_a_wrong_expectation(self):
        with self.assertRaises(AssertionError):
            self.assert_matrix("get", "/api/lookups/services/", {"*": 403})


class SeedDemoDataTests(TestCase):
    def run_seed(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("seed_demo_data", stdout=StringIO())

    def test_refuses_outside_development(self):
        from django.core.management.base import CommandError
        from django.test import override_settings

        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            self.run_seed()
        with override_settings(DEBUG=True), self.settings():
            import os
            os.environ["DJANGO_ENV"] = "production"
            try:
                with self.assertRaises(CommandError):
                    self.run_seed()
            finally:
                del os.environ["DJANGO_ENV"]

    def test_runs_twice_without_duplicating(self):
        from django.test import override_settings

        from accounts.models import User
        from leads.models import Lead

        with override_settings(DEBUG=True):
            self.run_seed()
            people, leads = User.objects.count(), Lead.objects.count()
            self.run_seed()
        self.assertEqual((User.objects.count(), Lead.objects.count()), (people, leads))
        self.assertGreaterEqual(leads, 7)
