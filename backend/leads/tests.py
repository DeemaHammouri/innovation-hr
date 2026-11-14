from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from audit.models import AuditEntry
from core.access import content_type_for
from core.models import DailyRun
from core.roles import ALL_ROLES
from core.testing import RoleCase
from leads import importer, reminders
from leads.models import ImportBatch, Interaction, Lead
from lookups.models import RejectionReason, SlaSetting
from notifications.models import Notification

CSV_HEADER = "company_name,contact_name,phone,email,source,notes\n"


def csv_file(text, name="leads.csv", encoding="utf-8"):
    return SimpleUploadedFile(name, text.encode(encoding), content_type="text/csv")


class LeadCase(RoleCase):
    def setUp(self):
        super().setUp()
        self.mkt, self.head, self.member = self.users["marketing"], self.users["commercial_head"], self.users["commercial_member"]
        self.member2 = self.make_user("member2@x.com", "Commercial", "member")
        self.reason = RejectionReason.objects.filter(is_active=True).first()
        self.n = 0

    def mk(self, status="new", assigned=None, **kw):
        self.n += 1
        data = dict(ref=f"LD-9{self.n:03d}", company_name=f"Company {self.n}", phone=f"07900000{self.n:02d}", created_by=self.mkt, status=status)
        if assigned:
            data.update(assigned_to=assigned, assigned_at=timezone.now())
        data.update(kw)
        return Lead.objects.create(**data)

    def today(self):
        return timezone.localdate()

    def day(self, n):
        return (self.today() + timedelta(days=n)).isoformat()

    def actions(self, lead):
        return list(AuditEntry.objects.filter(content_type=content_type_for(Lead), object_id=lead.pk).order_by("id").values_list("action", flat=True))


class AccessTests(LeadCase):
    def test_list_is_for_the_four_lead_roles(self):
        self.assert_matrix("get", "/api/leads/", {"ceo": 200, "marketing": 200, "commercial_head": 200, "commercial_member": 200, "*": 403})

    def test_create_is_marketing_only(self):
        body = {"company_name": "Acme", "phone": "0791112233"}
        for key in ALL_ROLES:
            Lead.objects.all().delete()  # fresh each time so duplicate detection doesn't hide a permission result
            self.as_role(key)
            res = self.client.post("/api/leads/", body, format="json")
            self.assertEqual(res.status_code, 201 if key == "marketing" else 403, key)

    def test_detail_visibility_by_role_and_assignment(self):
        lead = self.mk()
        url = f"/api/leads/{lead.pk}/"
        self.assert_matrix("get", url, {"ceo": 200, "marketing": 200, "commercial_head": 200, "commercial_member": 404, "hr_head": 403, "hr_member": 403, "operation_head": 403, "operation_member": 403})
        lead.assigned_to = self.member
        lead.save()
        self.as_role("commercial_member")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.as_user(self.member2)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_member_list_only_contains_their_leads_and_marketing_only_their_own(self):
        mine, theirs, unassigned = self.mk(assigned=self.member), self.mk(assigned=self.member2), self.mk()
        other = self.mk(created_by=self.head)  # not added by Marketing
        self.as_role("commercial_member")
        self.assertEqual({r["id"] for r in self.client.get("/api/leads/").data["results"]}, {mine.pk})
        self.as_role("marketing")
        self.assertEqual({r["id"] for r in self.client.get("/api/leads/").data["results"]}, {mine.pk, theirs.pk, unassigned.pk})
        self.assertEqual(self.client.get(f"/api/leads/{other.pk}/").status_code, 404)
        self.as_role("ceo")
        self.assertEqual(self.client.get("/api/leads/").data["count"], 4)

    def test_assign_is_head_only(self):
        lead = self.mk()
        self.assert_matrix("post", f"/api/leads/{lead.pk}/assign/", {"commercial_head": 200, "*": 403}, data={"assigned_to": self.member.pk})

    def test_assignee_list_is_head_only(self):
        self.assert_matrix("get", "/api/leads/assignees/", {"commercial_head": 200, "*": 403})

    def test_logging_a_contact_needs_the_head_or_the_assigned_member(self):
        lead = self.mk(assigned=self.member)
        url = f"/api/leads/{lead.pk}/interactions/"
        body = {"type": "call", "notes": "Spoke to them"}
        self.assert_matrix("post", url, {"ceo": 403, "marketing": 403, "commercial_head": 201, "commercial_member": 201, "*": 403}, data=body)
        self.as_user(self.member2)
        self.assertEqual(self.client.post(url, body, format="json").status_code, 404)

    def test_outcome_permissions(self):
        lead = self.mk(status="contacted", assigned=self.member)
        url = f"/api/leads/{lead.pk}/outcome/"
        body = {"outcome": "accepted"}
        for key in ("ceo", "marketing", "hr_head", "operation_head"):
            self.as_role(key)
            self.assertEqual(self.client.post(url, body, format="json").status_code, 403, key)
        self.as_user(self.member2)
        self.assertEqual(self.client.post(url, body, format="json").status_code, 404)
        self.as_role("commercial_member")
        self.assertEqual(self.client.post(url, body, format="json").status_code, 200)

    def test_reopen_and_restore_are_head_only(self):
        rejected = self.mk(status="rejected", assigned=self.member, rejection_reason=self.reason)
        self.assert_matrix("post", f"/api/leads/{rejected.pk}/reopen/", {"commercial_head": 200, "*": 403}, data={"note": "They called back"})
        archived = self.mk(archived_at=timezone.now())
        self.assert_matrix("post", f"/api/leads/{archived.pk}/restore/", {"commercial_head": 200, "*": 403})

    def test_archive_rules(self):
        lead = self.mk(assigned=self.member)
        for user in (self.users["ceo"], self.member, self.users["hr_head"]):
            self.as_user(user)
            self.assertEqual(self.client.post(f"/api/leads/{lead.pk}/archive/", {"reason": "x"}, format="json").status_code, 403)
        self.as_role("marketing")  # their own, still new, nobody has contacted it
        self.assertEqual(self.client.post(f"/api/leads/{lead.pk}/archive/", {"reason": "Added by mistake"}, format="json").status_code, 200)
        contacted = self.mk(status="contacted", assigned=self.member)
        Interaction.objects.create(lead=contacted, type="call", occurred_at=timezone.now(), created_by=self.member)
        self.assertEqual(self.client.post(f"/api/leads/{contacted.pk}/archive/", {"reason": "x"}, format="json").status_code, 403)
        self.as_role("commercial_head")
        self.assertEqual(self.client.post(f"/api/leads/{contacted.pk}/archive/", {"reason": "Duplicate company"}, format="json").status_code, 200)

    def test_archive_needs_a_reason_and_is_never_a_delete(self):
        lead = self.mk()
        self.as_role("commercial_head")
        self.assertEqual(self.client.post(f"/api/leads/{lead.pk}/archive/", {"reason": "  "}, format="json").status_code, 400)
        self.assertEqual(self.client.delete(f"/api/leads/{lead.pk}/").status_code, 405)
        self.client.post(f"/api/leads/{lead.pk}/archive/", {"reason": "Out of scope"}, format="json")
        self.assertTrue(Lead.objects.filter(pk=lead.pk, archived_at__isnull=False).exists())
        self.assertEqual(self.client.get(f"/api/leads/{lead.pk}/").status_code, 200)  # an archived lead still opens

    def test_edit_rules(self):
        lead = self.mk(assigned=self.member)
        body = {"contact_name": "New Person"}
        self.as_role("ceo")
        self.assertEqual(self.client.patch(f"/api/leads/{lead.pk}/", body, format="json").status_code, 403)
        self.as_role("marketing")  # own and still new
        self.assertEqual(self.client.patch(f"/api/leads/{lead.pk}/", body, format="json").status_code, 200)
        lead.status = "contacted"
        lead.save()
        self.assertEqual(self.client.patch(f"/api/leads/{lead.pk}/", body, format="json").status_code, 403)
        self.as_role("commercial_member")
        self.assertEqual(self.client.patch(f"/api/leads/{lead.pk}/", {"phone": "0795556677"}, format="json").status_code, 200)
        self.assertEqual(Lead.objects.get(pk=lead.pk).phone_key, "795556677")

    def test_server_tells_the_screen_what_is_allowed(self):
        lead = self.mk(assigned=self.member)
        self.as_role("commercial_head")
        p = self.client.get(f"/api/leads/{lead.pk}/").data["permissions"]
        self.assertTrue(p["can_assign"] and p["can_log"] and p["can_edit"] and p["can_archive"])
        self.assertFalse(p["can_reopen"] or p["can_restore"])
        self.as_role("ceo")
        p = self.client.get(f"/api/leads/{lead.pk}/").data["permissions"]
        self.assertFalse(any(p.values()))

    def test_blocked_while_password_change_is_pending(self):
        self.mkt.must_change_password = True
        self.mkt.save()
        self.as_role("marketing")
        self.assertEqual(self.client.get("/api/leads/").status_code, 403)


class StateMachineTests(LeadCase):
    def log(self, lead, user=None, **body):
        self.as_user(user or self.head)
        body.setdefault("type", "call")
        return self.client.post(f"/api/leads/{lead.pk}/interactions/", body, format="json")

    def outcome(self, lead, user=None, **body):
        self.as_user(user or self.head)
        return self.client.post(f"/api/leads/{lead.pk}/outcome/", body, format="json")

    def test_first_contact_moves_new_to_contacted(self):
        lead = self.mk(assigned=self.member)
        res = self.log(lead, notes="Hello")
        self.assertEqual(res.status_code, 201, res.data)
        lead.refresh_from_db()
        self.assertEqual(lead.status, "contacted")
        self.assertIsNotNone(lead.first_contacted_at)
        self.assertEqual(self.actions(lead), ["interaction", "contacted"])

    def test_contact_with_outcome_in_one_step(self):
        for outcome, extra, expected in (
            ("waiting", {"next_follow_up": self.day(3)}, "waiting"),
            ("rejected", {"rejection_reason": self.reason.pk, "rejection_note": "Too pricey"}, "rejected"),
            ("accepted", {}, "qualified"),
        ):
            lead = self.mk(assigned=self.member)
            res = self.log(lead, outcome=outcome, **extra)
            self.assertEqual(res.status_code, 201, res.data)
            self.assertEqual(res.data["status"], expected)

    def test_waiting_needs_a_date_that_is_today_or_later_within_a_year(self):
        lead = self.mk(assigned=self.member)
        self.assertEqual(self.log(lead, outcome="waiting").data["next_follow_up"], ["Choose a follow-up date."])
        self.assertEqual(self.log(lead, outcome="waiting", next_follow_up=self.day(-1)).status_code, 400)
        self.assertEqual(self.log(lead, outcome="waiting", next_follow_up=self.day(400)).status_code, 400)
        self.assertEqual(Interaction.objects.count(), 0)  # a refused request leaves nothing behind
        lead.refresh_from_db()
        self.assertEqual(lead.status, "new")
        self.assertEqual(self.log(lead, outcome="waiting", next_follow_up=self.day(0)).status_code, 201)

    def test_rejected_needs_an_active_reason_from_the_lookup(self):
        lead = self.mk(assigned=self.member)
        self.assertIn("rejection_reason", self.log(lead, outcome="rejected").data)
        self.assertEqual(self.log(lead, outcome="rejected", rejection_reason=99999).status_code, 400)
        self.reason.is_active = False
        self.reason.save()
        self.assertEqual(self.log(lead, outcome="rejected", rejection_reason=self.reason.pk).status_code, 400)

    def test_unknown_outcome_and_type_are_refused(self):
        lead = self.mk(assigned=self.member)
        self.assertEqual(self.log(lead, outcome="maybe").status_code, 400)
        self.assertEqual(self.log(lead, type="telepathy").status_code, 400)

    def test_outcome_endpoint_needs_a_first_contact(self):
        lead = self.mk(assigned=self.member)
        res = self.outcome(lead, outcome="accepted")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["detail"], "Log the first contact before recording an outcome.")

    def test_contacted_to_each_outcome(self):
        lead = self.mk(status="contacted", assigned=self.member, first_contacted_at=timezone.now())
        self.assertEqual(self.outcome(lead, outcome="waiting", next_follow_up=self.day(2)).data["status"], "waiting")
        self.assertEqual(self.outcome(lead, outcome="accepted").data["status"], "qualified")
        lead.refresh_from_db()
        self.assertIsNone(lead.next_follow_up)
        self.assertIsNotNone(lead.qualified_at)

    def test_a_waiting_lead_must_come_out_of_every_contact_with_an_outcome(self):
        lead = self.mk(status="waiting", assigned=self.member, next_follow_up=self.today())
        res = self.log(lead, notes="No answer")
        self.assertEqual(res.status_code, 400)
        self.assertIn("outcome", res.data)
        res = self.log(lead, outcome="waiting", next_follow_up=self.day(5))
        self.assertEqual(res.data["next_follow_up"], self.day(5))

    def test_closed_leads_accept_nothing(self):
        for st in ("qualified", "rejected"):
            lead = self.mk(status=st, assigned=self.member, rejection_reason=self.reason if st == "rejected" else None)
            self.assertEqual(self.log(lead).status_code, 400, st)
            self.assertEqual(self.outcome(lead, outcome="accepted").status_code, 400, st)

    def test_a_contact_cannot_be_in_the_future(self):
        lead = self.mk(assigned=self.member)
        later = (timezone.now() + timedelta(hours=3)).isoformat()
        self.assertEqual(self.log(lead, occurred_at=later).status_code, 400)

    def test_archived_leads_refuse_changes(self):
        lead = self.mk(assigned=self.member, archived_at=timezone.now())
        self.assertEqual(self.log(lead).status_code, 403)  # can_pipeline_write is false for archived leads
        self.as_role("commercial_head")
        self.assertEqual(self.client.post(f"/api/leads/{lead.pk}/assign/", {"assigned_to": self.member2.pk}, format="json").status_code, 400)

    def test_reopen(self):
        lead = self.mk(status="rejected", assigned=self.member, rejection_reason=self.reason, rejection_note="no", rejected_at=timezone.now())
        self.as_role("commercial_head")
        url = f"/api/leads/{lead.pk}/reopen/"
        self.assertEqual(self.client.post(url, {"note": " "}, format="json").status_code, 400)
        res = self.client.post(url, {"note": "They called back"}, format="json")
        self.assertEqual(res.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual((lead.status, lead.rejection_reason, lead.rejection_note), ("contacted", None, ""))
        self.assertTrue(Notification.objects.filter(user=self.member, kind="lead_reopened").exists())
        self.assertEqual(self.client.post(url, {"note": "again"}, format="json").status_code, 400)  # no longer rejected
        entry = AuditEntry.objects.filter(object_id=lead.pk, action="reopened").get()
        self.assertEqual((entry.from_value, entry.to_value, entry.comment), ("rejected", "contacted", "They called back"))

    def test_qualified_leads_cannot_be_reopened(self):
        lead = self.mk(status="qualified", assigned=self.member)
        self.as_role("commercial_head")
        self.assertEqual(self.client.post(f"/api/leads/{lead.pk}/reopen/", {"note": "x"}, format="json").status_code, 400)

    def test_assign_and_reassign(self):
        lead = self.mk()
        self.as_role("commercial_head")
        url = f"/api/leads/{lead.pk}/assign/"
        self.assertEqual(self.client.post(url, {"assigned_to": self.users["hr_head"].pk}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"assigned_to": "abc"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"assigned_to": self.member.pk}, format="json").status_code, 200)
        self.assertEqual(Notification.objects.filter(user=self.member, kind="assigned").count(), 1)
        self.client.post(url, {"assigned_to": self.member.pk}, format="json")  # same person again: nothing new
        self.assertEqual(Notification.objects.filter(user=self.member, kind="assigned").count(), 1)
        self.client.post(url, {"assigned_to": self.member2.pk}, format="json")
        self.assertEqual(self.actions(lead), ["assigned", "assigned"])
        last = AuditEntry.objects.filter(object_id=lead.pk).first()
        self.assertEqual((last.from_value, last.to_value), (self.member.full_name, self.member2.full_name))
        self.member2.is_active = False
        self.member2.save()
        self.assertEqual(self.client.post(url, {"assigned_to": self.member2.pk}, format="json").status_code, 400)

    def test_head_assigning_themselves_sends_no_notification(self):
        lead = self.mk()
        self.as_role("commercial_head")
        self.client.post(f"/api/leads/{lead.pk}/assign/", {"assigned_to": self.head.pk}, format="json")
        self.assertFalse(Notification.objects.filter(user=self.head, kind="assigned").exists())

    def test_head_hears_about_outcomes_from_members_but_not_their_own(self):
        a, b = self.mk(status="contacted", assigned=self.member), self.mk(status="contacted", assigned=self.head)
        self.outcome(a, user=self.member, outcome="accepted")
        self.outcome(b, user=self.head, outcome="accepted")
        self.assertEqual(Notification.objects.filter(user=self.head, kind="lead_qualified").count(), 1)
        c = self.mk(status="contacted", assigned=self.member)
        self.outcome(c, user=self.member, outcome="rejected", rejection_reason=self.reason.pk)
        self.assertTrue(Notification.objects.filter(user=self.head, kind="lead_rejected").exists())

    def test_full_audit_trail_of_a_journey(self):
        lead = self.mk(assigned=self.member)
        self.log(lead, user=self.member, outcome="waiting", next_follow_up=self.day(1))
        self.log(lead, user=self.member, outcome="accepted")
        self.assertEqual(self.actions(lead), ["interaction", "contacted", "outcome_waiting", "interaction", "outcome_qualified"])
        self.as_role("commercial_member")
        timeline = self.client.get(f"/api/activity/?target=lead:{lead.pk}").data["results"]
        self.assertEqual(timeline[0]["action"], "outcome_qualified")
        self.assertEqual(timeline[0]["actor_name"], self.member.full_name)


class CreateAndDuplicateTests(LeadCase):
    def post(self, **over):
        self.as_role("marketing")
        body = {"company_name": "Acme Co", "contact_name": "Sam", "phone": "+962 79 123 4567", "email": "sam@acme.example"}
        body.update(over)
        return self.client.post("/api/leads/", body, format="json")

    def test_create_gives_a_readable_reference_and_logs_it(self):
        res = self.post()
        self.assertEqual(res.status_code, 201)
        self.assertRegex(res.data["ref"], r"^LD-\d{4}$")
        self.assertEqual((res.data["status"], res.data["created_by_name"]), ("new", self.mkt.full_name))
        self.assertEqual(self.actions(Lead.objects.get(pk=res.data["id"])), ["created"])

    def test_refs_count_up(self):
        a, b = self.post(phone="0790000001", email="a@x.com"), self.post(phone="0790000002", email="b@x.com")
        self.assertEqual(int(b.data["ref"][3:]) - int(a.data["ref"][3:]), 1)

    def test_head_is_told_about_new_leads(self):
        self.post()
        n = Notification.objects.get(user=self.head, kind="leads_new")
        self.assertEqual(n.link, "/pipeline")

    def test_validation_messages(self):
        self.assertIn("company_name", self.post(company_name=" ").data)
        self.assertIn("email", self.post(email="not-an-email", phone="").data)
        self.assertIn("phone", self.post(phone="12", email="").data)
        self.assertIn("phone", self.post(phone="abc-defg-hij", email="").data)
        self.assertEqual(self.post(phone="", email="").data["phone"], ["Add a phone number or an email so someone can reach this lead."])
        self.assertIn("company_name", self.post(company_name="x" * 201).data)

    def test_arabic_text_is_kept(self):
        res = self.post(company_name="شركة الأفق", contact_name="خالد العتيبي")
        self.assertEqual(Lead.objects.get(pk=res.data["id"]).company_name, "شركة الأفق")

    def test_duplicate_by_phone_in_any_format(self):
        self.post()
        res = self.post(company_name="Other", email="", phone="0791234567")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["duplicate"], [Lead.objects.first().ref])

    def test_duplicate_by_email_ignores_case_and_spaces(self):
        self.post()
        self.assertEqual(self.post(company_name="Other", phone="", email=" SAM@ACME.example ").status_code, 400)

    def test_duplicate_can_be_confirmed_on_purpose(self):
        self.post()
        res = self.post(company_name="Same person, second company", allow_duplicate=True)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Lead.objects.count(), 2)

    def test_archived_leads_do_not_block_a_new_one(self):
        first = self.post().data["id"]
        Lead.objects.filter(pk=first).update(archived_at=timezone.now())
        self.assertEqual(self.post().status_code, 201)

    def test_very_short_numbers_are_never_duplicates(self):
        self.mk(phone="123456", email="")
        self.assertEqual(self.post(phone="123456", email="", company_name="x").status_code, 400)  # invalid (under 7 digits), not "duplicate"


class ImportTests(LeadCase):
    def preview(self, text, **kw):
        self.as_role("marketing")
        return self.client.post("/api/leads/import/preview/", {"file": csv_file(text, **kw)}, format="multipart")

    def confirm(self, text, **extra):
        self.as_role("marketing")
        return self.client.post("/api/leads/import/confirm/", {"file": csv_file(text), **extra}, format="multipart")

    GOOD = CSV_HEADER + "Al Noor,Hassan,0791000001,h@alnoor.example,Fair,\nCedar,Maya,0791000002,,,Call back\n"

    def test_marketing_only(self):
        for key in ALL_ROLES:
            self.as_role(key)
            expected = 200 if key == "marketing" else 403
            self.assertEqual(self.client.get("/api/leads/import/template/").status_code, expected, key)
            res = self.client.post("/api/leads/import/preview/", {"file": csv_file(self.GOOD)}, format="multipart")
            self.assertEqual(res.status_code, expected, key)
            res = self.client.post("/api/leads/import/confirm/", {"file": csv_file(self.GOOD)}, format="multipart")
            self.assertEqual(res.status_code, 403 if key != "marketing" else 201, key)
            Lead.objects.all().delete()
            ImportBatch.objects.all().delete()

    def test_template_downloads_and_imports_cleanly(self):
        self.as_role("marketing")
        res = self.client.get("/api/leads/import/template/")
        self.assertIn("attachment", res["Content-Disposition"])
        body = res.content.decode("utf-8-sig")
        self.assertTrue(body.startswith("company_name,contact_name,phone,email,source,notes"))
        out = self.preview(body)
        self.assertEqual(out.data["summary"], {"total": 2, "ok": 2, "errors": 0, "duplicates": 0})

    def test_preview_writes_nothing(self):
        self.preview(self.GOOD)
        self.assertEqual((Lead.objects.count(), ImportBatch.objects.count()), (0, 0))

    def test_row_numbers_match_the_spreadsheet_and_blank_rows_are_skipped(self):
        out = self.preview(CSV_HEADER + "A,,0791000001,,,\n,,,,,\n,,,,,\nB,,0791000002,,,\n")
        self.assertEqual([r["row"] for r in out.data["rows"]], [2, 5])

    def test_row_level_errors(self):
        out = self.preview(CSV_HEADER + ",Nobody,0791000001,,,\nX,,,,,\nY,,12,,,\nZ,,,bad-email,,\nOK,,0791000009,,,\n")
        states = [r["state"] for r in out.data["rows"]]
        self.assertEqual(states, ["error", "error", "error", "error", "ok"])
        self.assertEqual(out.data["rows"][0]["errors"][0]["field"], "company_name")
        self.assertEqual(out.data["summary"]["errors"], 4)

    def test_duplicates_inside_the_file_and_against_existing_leads(self):
        existing = self.mk(phone="+962 79 100 0001")
        out = self.preview(CSV_HEADER + "A,,0791000001,,,\nB,,0791000002,b@x.com,,\nC,,0791000002,,,\nD,,,B@X.COM,,\n")
        rows = out.data["rows"]
        self.assertEqual((rows[0]["state"], rows[0]["duplicate_of"]), ("duplicate", existing.ref))
        self.assertEqual(rows[1]["state"], "ok")
        self.assertEqual((rows[2]["state"], rows[2]["duplicate_in_file"]), ("duplicate", 3))
        self.assertEqual((rows[3]["state"], rows[3]["duplicate_in_file"]), ("duplicate", 3))

    def test_excel_style_files_bom_semicolons_aliases_arabic(self):
        text = "﻿Company;Contact Name;Mobile;E-mail\nشركة الأفق;خالد;0791000001;k@ufuq.example\n"
        out = self.preview(text)
        self.assertEqual(out.status_code, 200, out.data)
        row = out.data["rows"][0]
        self.assertEqual((row["company_name"], row["contact_name"], row["phone"], row["email"]), ("شركة الأفق", "خالد", "0791000001", "k@ufuq.example"))

    def test_short_rows_and_extra_columns_are_tolerated(self):
        out = self.preview("company_name,phone,extra\nA,0791000001\nB,0791000002,ignored,more\n")
        self.assertEqual(out.data["summary"]["ok"], 2)

    def test_quoted_commas_and_newlines(self):
        out = self.preview(CSV_HEADER + '"Acme, Inc.",Sam,0791000001,,,"Line one\nLine two"\n')
        self.assertEqual(out.data["rows"][0]["company_name"], "Acme, Inc.")
        self.assertIn("Line two", out.data["rows"][0]["notes"])

    def test_file_level_problems(self):
        cases = {
            "wrong extension": (self.preview(self.GOOD, name="leads.xlsx"), importer.MSG_EXT),
            "no company column": (self.preview("name_only,phone\nA,0791000001\n".replace("name_only", "city")), importer.MSG_COLUMNS),
            "only a header": (self.preview(CSV_HEADER), importer.MSG_EMPTY),
            "empty file": (self.preview(""), importer.MSG_EMPTY),
            "only blank rows": (self.preview(CSV_HEADER + ",,,,,\n,,,,,\n"), importer.MSG_EMPTY),
            "not utf-8": (self.preview(CSV_HEADER + "Caf\xe9,,0791000001,,,\n", encoding="latin-1"), importer.MSG_ENCODING),
        }
        for name, (res, message) in cases.items():
            self.assertEqual(res.status_code, 400, name)
            self.assertEqual(res.data["file"], [message], name)

    def test_binary_file_is_refused(self):
        self.as_role("marketing")
        res = self.client.post("/api/leads/import/preview/", {"file": SimpleUploadedFile("x.csv", b"a,b\n\x00\x01\x02")}, format="multipart")
        self.assertEqual(res.status_code, 400)

    def test_missing_file(self):
        self.as_role("marketing")
        self.assertEqual(self.client.post("/api/leads/import/preview/", {}, format="multipart").status_code, 400)

    def test_row_and_size_limits(self):
        many = CSV_HEADER + "".join(f"Co {i},,07910{i:05d},,,\n" for i in range(importer.MAX_ROWS + 1))
        self.assertEqual(self.preview(many).data["file"], [importer.MSG_ROWS])
        exactly = CSV_HEADER + "".join(f"Co {i},,07910{i:05d},,,\n" for i in range(importer.MAX_ROWS))
        self.assertEqual(self.preview(exactly).data["summary"]["total"], importer.MAX_ROWS)
        huge = CSV_HEADER + "A,," + "9" * (importer.MAX_BYTES) + ",,,\n"
        self.assertEqual(self.preview(huge).data["file"], [importer.MSG_SIZE])

    def test_confirm_creates_one_batch_with_leads_audit_and_a_notification(self):
        res = self.confirm(self.GOOD)
        self.assertEqual(res.status_code, 201, res.data)
        batch = ImportBatch.objects.get()
        self.assertEqual((batch.imported_count, batch.total_rows, batch.status), (2, 2, "active"))
        self.assertRegex(batch.ref, r"^IB-\d{4}$")
        leads = list(Lead.objects.filter(batch=batch).order_by("ref"))
        self.assertEqual([l.company_name for l in leads], ["Al Noor", "Cedar"])
        self.assertEqual(int(leads[1].ref[3:]) - int(leads[0].ref[3:]), 1)
        self.assertTrue(all(l.created_by == self.mkt and l.status == "new" and l.phone_key for l in leads))
        self.assertEqual(self.actions(leads[0]), ["imported"])
        n = Notification.objects.get(user=self.head, kind="leads_new")
        self.assertIn("2", n.title)

    def test_confirm_skips_errors_and_duplicates_by_default_and_can_import_duplicates(self):
        self.mk(phone="0791000001")
        text = CSV_HEADER + "Dup,,0791000001,,,\nBad,,,,,\nGood,,0791000005,,,\n"
        batch = ImportBatch.objects.get(pk=self.confirm(text).data["id"])
        self.assertEqual((batch.imported_count, batch.skipped_errors, batch.skipped_duplicates), (1, 1, 1))
        batch2 = ImportBatch.objects.get(pk=self.confirm(text, duplicates="import").data["id"])
        self.assertEqual(batch2.imported_count, 2)  # the duplicate of the original and the earlier "Good" row both come in
        self.assertEqual(batch2.skipped_errors, 1)

    def test_confirm_with_nothing_importable_is_refused(self):
        res = self.confirm(CSV_HEADER + "Bad,,,,,\n")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(ImportBatch.objects.count(), 0)

    def test_confirm_is_all_or_nothing_for_a_bad_file(self):
        self.assertEqual(self.confirm("nonsense").status_code, 400)
        self.assertEqual((Lead.objects.count(), ImportBatch.objects.count()), (0, 0))

    def test_undo_while_nobody_has_contacted_them(self):
        batch = ImportBatch.objects.get(pk=self.confirm(self.GOOD).data["id"])
        self.as_role("marketing")
        res = self.client.post(f"/api/import-batches/{batch.pk}/undo/")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], "undone")
        self.assertEqual(Lead.objects.filter(batch=batch, archived_at__isnull=False).count(), 2)  # archived, never deleted
        self.assertEqual(Lead.objects.filter(batch=batch).count(), 2)
        self.assertEqual(self.client.get("/api/leads/").data["count"], 0)
        self.assertEqual(self.client.post(f"/api/import-batches/{batch.pk}/undo/").status_code, 400)
        self.assertIn("archived", self.actions(Lead.objects.filter(batch=batch).first()))
        # the same file can be imported again: archived leads don't count as duplicates
        self.assertEqual(self.preview(self.GOOD).data["summary"]["duplicates"], 0)

    def test_assigning_a_lead_does_not_block_undo_but_contacting_it_does(self):
        batch = ImportBatch.objects.get(pk=self.confirm(self.GOOD).data["id"])
        lead = Lead.objects.filter(batch=batch).first()
        self.as_role("commercial_head")
        self.client.post(f"/api/leads/{lead.pk}/assign/", {"assigned_to": self.member.pk}, format="json")
        self.as_role("marketing")
        self.assertEqual(self.client.post(f"/api/import-batches/{batch.pk}/undo/").status_code, 200)  # assigned, but nobody contacted it
        batch2 = ImportBatch.objects.get(pk=self.confirm(CSV_HEADER + "Other,,0791009999,,,\n").data["id"])
        lead2 = Lead.objects.get(batch=batch2)
        lead2.assigned_to, lead2.assigned_at = self.member, timezone.now()
        lead2.save()
        self.as_user(self.member)
        self.client.post(f"/api/leads/{lead2.pk}/interactions/", {"type": "call"}, format="json")
        self.as_role("marketing")
        res = self.client.post(f"/api/import-batches/{batch2.pk}/undo/")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["detail"], importer.MSG_UNDO_CONTACTED)
        self.assertEqual(Lead.objects.filter(batch=batch2, archived_at__isnull=True).count(), 1)

    def test_batches_are_scoped_and_only_their_owner_can_undo(self):
        mine = ImportBatch.objects.get(pk=self.confirm(self.GOOD).data["id"])
        theirs = ImportBatch.objects.create(ref="IB-0099", filename="x.csv", created_by=self.head)
        self.as_role("marketing")
        self.assertEqual({b["id"] for b in self.client.get("/api/import-batches/").data["results"]}, {mine.pk})
        self.assertEqual(self.client.get(f"/api/import-batches/{theirs.pk}/").status_code, 404)
        for key in ("ceo", "commercial_head"):
            self.as_role(key)
            self.assertEqual(self.client.get("/api/import-batches/").data["count"], 2, key)
            self.assertEqual(self.client.post(f"/api/import-batches/{mine.pk}/undo/").status_code, 403, key)
        self.assert_matrix("get", "/api/import-batches/", {"ceo": 200, "marketing": 200, "commercial_head": 200, "*": 403})

    def test_batch_numbers(self):
        batch = self.confirm(self.GOOD).data
        self.assertEqual((batch["contacted_count"], batch["can_undo"]), (0, True))
        self.as_role("commercial_head")
        self.assertFalse(self.client.get(f"/api/import-batches/{batch['id']}/").data["can_undo"])


class SlaReminderAndMyWorkTests(LeadCase):
    def test_flags(self):
        SlaSetting.objects.update_or_create(pk=1, defaults={"first_contact_hours": 24, "follow_up_days": 3})
        fresh = self.mk(assigned=self.member)
        stale = self.mk(assigned=self.member, assigned_at=timezone.now() - timedelta(hours=30))
        late = self.mk(status="waiting", assigned=self.member, next_follow_up=self.today() - timedelta(days=2))
        ontime = self.mk(status="waiting", assigned=self.member, next_follow_up=self.today())
        self.as_role("commercial_head")
        rows = {r["id"]: r for r in self.client.get("/api/leads/").data["results"]}
        self.assertEqual([rows[l.pk]["first_contact_overdue"] for l in (fresh, stale)], [False, True])
        self.assertEqual([rows[l.pk]["follow_up_overdue"] for l in (late, ontime)], [True, False])
        self.assertEqual({r["id"] for r in self.client.get("/api/leads/?overdue=1").data["results"]}, {late.pk})

    def test_an_unassigned_lead_is_measured_from_when_it_was_added(self):
        SlaSetting.objects.update_or_create(pk=1, defaults={"first_contact_hours": 1, "follow_up_days": 3})
        lead = self.mk()
        Lead.objects.filter(pk=lead.pk).update(created_at=timezone.now() - timedelta(hours=2))
        self.as_role("commercial_head")
        self.assertTrue(self.client.get(f"/api/leads/{lead.pk}/").data["first_contact_overdue"])

    def test_reminders_fire_once(self):
        SlaSetting.objects.update_or_create(pk=1, defaults={"first_contact_hours": 1, "follow_up_days": 3})
        late = self.mk(status="waiting", assigned=self.member, next_follow_up=self.today() - timedelta(days=1))
        stale = self.mk(assigned=self.member2, assigned_at=timezone.now() - timedelta(hours=5))
        orphan = self.mk()
        Lead.objects.filter(pk=orphan.pk).update(created_at=timezone.now() - timedelta(hours=5))
        self.assertEqual(reminders.run(), 3)
        self.assertEqual(reminders.run(), 0)
        self.assertTrue(Notification.objects.filter(user=self.member, kind="followup_overdue", link=f"/leads/{late.pk}").exists())
        self.assertTrue(Notification.objects.filter(user=self.member2, kind="first_contact_overdue").exists())
        self.assertTrue(Notification.objects.filter(user=self.head, kind="assign_needed").exists())
        # a new follow-up date that goes overdue again is a new reminder
        Lead.objects.filter(pk=late.pk).update(next_follow_up=self.today() - timedelta(days=3))
        self.assertEqual(reminders.run(), 1)

    def test_reminders_skip_archived_closed_and_future(self):
        self.mk(status="waiting", assigned=self.member, next_follow_up=self.today() - timedelta(days=1), archived_at=timezone.now())
        self.mk(status="qualified", assigned=self.member)
        self.mk(status="waiting", assigned=self.member, next_follow_up=self.today())
        self.assertEqual(reminders.run(), 0)

    def test_reminders_are_in_the_recipients_language(self):
        self.member.preferred_language = "ar"
        self.member.save()
        self.mk(status="waiting", assigned=self.member, next_follow_up=self.today() - timedelta(days=1))
        reminders.run()
        self.assertTrue(Notification.objects.get(user=self.member).title.startswith("متابعة متأخرة"))

    def test_daily_job_runs_once_per_day_on_the_first_request(self):
        self.mk(status="waiting", assigned=self.member, next_follow_up=self.today() - timedelta(days=1))
        self.as_role("commercial_member")
        self.client.get("/api/my-work/")
        self.client.get("/api/my-work/")
        self.assertEqual(DailyRun.objects.filter(name="lead_reminders").count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.member, kind="followup_overdue").count(), 1)

    def test_my_work_for_the_head(self):
        unassigned = self.mk()
        mine_new = self.mk(assigned=self.head)
        self.mk(assigned=self.member)  # someone else's: not on the head's list
        self.as_role("commercial_head")
        data = self.client.get("/api/my-work/").data
        kinds = {(i["kind"], i["ref"]) for i in data["items"]}
        self.assertEqual(kinds, {("lead_assign", unassigned.ref), ("lead_contact", mine_new.ref)})
        self.assertEqual(data["badges"], {"pipeline": 2})

    def test_my_work_for_a_member_is_ordered_overdue_first(self):
        contact = self.mk(assigned=self.member)
        due = self.mk(status="waiting", assigned=self.member, next_follow_up=self.today())
        late = self.mk(status="waiting", assigned=self.member, next_follow_up=self.today() - timedelta(days=4))
        pending = self.mk(status="contacted", assigned=self.member)
        self.mk(status="waiting", assigned=self.member, next_follow_up=self.today() + timedelta(days=4))  # not yet due
        self.mk(assigned=self.member2)
        self.as_role("commercial_member")
        items = self.client.get("/api/my-work/").data["items"]
        self.assertEqual(items[0]["ref"], late.ref)
        self.assertEqual({(i["kind"], i["ref"]) for i in items}, {("lead_contact", contact.ref), ("followup_due", due.ref), ("followup_overdue", late.ref), ("lead_outcome", pending.ref)})
        self.assertEqual(items[0]["link"], f"/leads/{late.pk}")

    def test_my_work_is_empty_for_other_roles(self):
        self.mk()
        for key in ("marketing", "ceo", "hr_head", "operation_head"):
            self.as_role(key)
            self.assertEqual(self.client.get("/api/my-work/").data["items"], [], key)


class ListBoardAndRegistryTests(LeadCase):
    def test_filters_search_ordering(self):
        a = self.mk(company_name="Alpha Trading", phone="0791110001", assigned=self.member)
        b = self.mk(company_name="Beta Logistics", phone="0791110002", status="waiting", next_follow_up=self.today() + timedelta(days=2))
        c = self.mk(company_name="Gamma", phone="0791110003", archived_at=timezone.now())
        self.as_role("commercial_head")
        ids = lambda q: [r["id"] for r in self.client.get(f"/api/leads/{q}").data["results"]]
        self.assertEqual(set(ids("")), {a.pk, b.pk})
        self.assertEqual(set(ids("?archived=1")), {a.pk, b.pk, c.pk})
        self.assertEqual(ids("?archived=only"), [c.pk])
        self.assertEqual(set(ids("?archived=")), {a.pk, b.pk})
        self.assertEqual(ids("?status=waiting"), [b.pk])
        self.assertEqual(set(ids("?status=new,waiting")), {a.pk, b.pk})
        self.assertEqual(ids("?assigned_to=none"), [b.pk])
        self.assertEqual(ids(f"?assigned_to={self.member.pk}"), [a.pk])
        self.assertEqual(ids("?search=logistics"), [b.pk])
        self.assertEqual(ids("?search=0791110001"), [a.pk])
        self.assertEqual(ids(f"?search={a.ref}"), [a.pk])
        self.assertEqual(ids("?ordering=company_name"), [a.pk, b.pk])
        self.assertEqual(ids("?ordering=-company_name"), [b.pk, a.pk])

    def test_batch_filter_and_pagination(self):
        batch = ImportBatch.objects.create(ref="IB-0001", filename="f.csv", created_by=self.mkt)
        for _ in range(3):
            self.mk(batch=batch)
        self.mk()
        self.as_role("commercial_head")
        self.assertEqual(self.client.get(f"/api/leads/?batch={batch.pk}").data["count"], 3)
        page = self.client.get("/api/leads/?page_size=2").data
        self.assertEqual((page["count"], len(page["results"])), (4, 2))

    def test_board_groups_by_stage_and_respects_visibility(self):
        self.mk(assigned=self.member)
        self.mk(status="waiting", assigned=self.member, next_follow_up=self.today())
        self.mk(status="qualified", assigned=self.member2)
        self.mk()
        self.as_role("commercial_head")
        cols = {c["status"]: c for c in self.client.get("/api/leads/board/").data["columns"]}
        self.assertEqual(list(cols), ["new", "contacted", "waiting", "qualified", "rejected"])
        self.assertEqual([cols[s]["count"] for s in cols], [2, 0, 1, 1, 0])
        self.as_role("commercial_member")
        cols = {c["status"]: c for c in self.client.get("/api/leads/board/").data["columns"]}
        self.assertEqual([cols[s]["count"] for s in cols], [1, 0, 1, 0, 0])
        self.assert_matrix("get", "/api/leads/board/", {"ceo": 200, "marketing": 200, "commercial_head": 200, "commercial_member": 200, "*": 403})

    def test_activity_comments_and_files_follow_the_lead(self):
        lead = self.mk(assigned=self.member)
        for path in ("activity", "comments"):
            self.as_user(self.member2)
            self.assertEqual(self.client.get(f"/api/{path}/?target=lead:{lead.pk}").status_code, 404, path)
            self.as_role("hr_head")
            self.assertEqual(self.client.get(f"/api/{path}/?target=lead:{lead.pk}").status_code, 404, path)
            for key in ("ceo", "marketing", "commercial_head", "commercial_member"):
                self.as_role(key)
                self.assertEqual(self.client.get(f"/api/{path}/?target=lead:{lead.pk}").status_code, 200, (path, key))

    def test_marketing_can_comment_and_mention_the_head_on_their_lead(self):
        lead = self.mk()
        self.as_role("marketing")
        res = self.client.post(f"/api/comments/?target=lead:{lead.pk}", {"body": "Hot lead", "mentions": [self.head.pk]}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertTrue(Notification.objects.filter(user=self.head, kind="mention").exists())
        bad = self.client.post(f"/api/comments/?target=lead:{lead.pk}", {"body": "x", "mentions": [self.member.pk]}, format="json")
        self.assertEqual(bad.status_code, 400)  # a member the lead isn't assigned to cannot open it

    def test_archived_leads_stop_taking_comments(self):
        lead = self.mk(assigned=self.member, archived_at=timezone.now())
        self.as_role("commercial_head")
        self.assertEqual(self.client.post(f"/api/comments/?target=lead:{lead.pk}", {"body": "late"}, format="json").status_code, 403)

    def test_list_cost_does_not_grow_with_the_number_of_leads(self):
        def cost():
            self.as_role("commercial_head")
            with CaptureQueriesContext(connection) as ctx:
                res = self.client.get("/api/leads/?page_size=100")
            self.assertEqual(res.status_code, 200)
            return len(ctx)

        for _ in range(3):
            self.mk(assigned=self.member)
        few = cost()
        for _ in range(30):
            self.mk(assigned=self.member2, status="waiting", next_follow_up=self.today())
        self.assertEqual(cost(), few)

    def test_board_cost_is_bounded(self):
        for i in range(20):
            self.mk(assigned=self.member, status=["new", "waiting", "contacted"][i % 3], next_follow_up=self.today())
        self.as_role("commercial_head")
        with CaptureQueriesContext(connection) as ctx:
            self.client.get("/api/leads/board/")
        self.assertLessEqual(len(ctx), 16)
