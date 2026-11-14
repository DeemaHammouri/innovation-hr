from datetime import timedelta

from django.core.files.base import ContentFile
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from audit.models import AuditEntry
from contracts import services
from contracts.models import Contract
from core.access import content_type_for
from core.roles import ALL_ROLES
from core.testing import RoleCase
from files.models import Attachment
from leads.models import Lead
from notifications.models import Notification

PIPELINE = ("commercial_head", "commercial_member")


class CCase(RoleCase):
    def setUp(self):
        super().setUp()
        self.mkt, self.head, self.member = self.users["marketing"], self.users["commercial_head"], self.users["commercial_member"]
        self.hr, self.hr2, self.ceo = self.users["hr_head"], self.users["hr_member"], self.users["ceo"]
        self.member2 = self.make_user("member2@x.com", "Commercial", "member")
        self.n = 0

    def lead(self, assigned=None, skipped=True, **kw):
        self.n += 1
        return Lead.objects.create(
            ref=f"LD-7{self.n:03d}", company_name=f"Client {self.n}", phone=f"07700000{self.n:02d}", created_by=self.mkt, status="qualified",
            assigned_to=assigned or self.member, assigned_at=timezone.now(), skipped_quotation_at=timezone.now() if skipped else None, **kw,
        )

    def attach(self, c, category, user=None):
        return Attachment.objects.create(
            file=ContentFile(b"%PDF-1.4 test", name="x.pdf"), original_name=f"{category}.pdf", content_type_header="application/pdf", size=13,
            category=category, uploaded_by=user or self.hr, content_type=content_type_for(Contract), object_id=c.pk,
        )

    def contract(self, state="requested", lead=None):
        """Walk a real contract to `state` through the services."""
        c = services.request_contract(self.member, lead or self.lead(), "Standard terms")
        if state == "requested":
            return Contract.objects.get(pk=c.pk)
        order = ["requested", "drafting", "with_commercial", "meeting_logged", "ceo_review", "signed", "handed_over"]
        if state == "returned":
            order = ["requested", "drafting", "with_commercial", "meeting_logged", "ceo_review"]
        for step in order[1:]:
            if step == "drafting":
                c = services.start_drafting(self.hr, c)
            elif step == "with_commercial":
                self.attach(c, "draft")
                c = services.send_to_commercial(self.hr, c)
            elif step == "meeting_logged":
                c = services.log_meeting(self.member, c, timezone.localdate(), "Met the owner")
            elif step == "ceo_review":
                self.attach(c, "visit_report", self.member)
                self.attach(c, "client_signed_copy", self.member)
                c = services.submit_to_ceo(self.member, c)
            elif step == "signed":
                c = services.ceo_sign(self.ceo, c)
            elif step == "handed_over":
                self.attach(c, "final_signed")
                c = services.hand_over(self.hr, c)
            if step == state:
                break
        if state == "returned":
            c = services.ceo_return(self.ceo, c, "Fix clause 4")
        return Contract.objects.get(pk=c.pk)

    def act(self, user, c, name, body=None):
        self.as_user(user)
        return self.client.post(f"/api/contracts/{c.pk}/{name}/", body or {}, format="json")

    def actions(self, c):
        return list(AuditEntry.objects.filter(content_type=content_type_for(Contract), object_id=c.pk).order_by("id").values_list("action", flat=True))


class AccessTests(CCase):
    def test_list_for_seven_roles(self):
        self.assert_matrix("get", "/api/contracts/", {"marketing": 403, "*": 200})

    def test_visibility(self):
        mine, theirs = self.contract(), self.contract(lead=self.lead(assigned=self.member2))
        done = self.contract("handed_over")
        self.as_role("commercial_member")
        self.assertEqual({r["id"] for r in self.client.get("/api/contracts/").data["results"]}, {mine.pk, done.pk})
        self.assertEqual(self.client.get(f"/api/contracts/{theirs.pk}/").status_code, 404)
        for key in ("ceo", "commercial_head", "hr_head", "hr_member"):
            self.as_role(key)
            self.assertEqual(self.client.get("/api/contracts/").data["count"], 3, key)
        for key in ("operation_head", "operation_member"):
            self.as_role(key)
            self.assertEqual({r["id"] for r in self.client.get("/api/contracts/").data["results"]}, {done.pk}, key)
            self.assertEqual(self.client.get(f"/api/contracts/{mine.pk}/").status_code, 404, key)
            self.assertEqual(self.client.get(f"/api/contracts/{done.pk}/").status_code, 200, key)
        self.as_role("marketing")
        self.assertEqual(self.client.get(f"/api/contracts/{mine.pk}/").status_code, 403)

    def test_comments_and_files_follow_the_contract(self):
        c = self.contract()
        for key in ("marketing", "operation_head"):
            self.as_role(key)
            self.assertIn(self.client.get(f"/api/comments/?target=contract:{c.pk}").status_code, (403, 404), key)
        self.as_user(self.member2)
        self.assertEqual(self.client.get(f"/api/files/?target=contract:{c.pk}").status_code, 404)

    def test_create_is_for_pipeline_only(self):
        lead = self.lead()
        for key in ALL_ROLES:
            Contract.objects.all().delete()
            self.as_role(key)
            res = self.client.post("/api/contracts/", {"lead": lead.pk}, format="json")
            self.assertEqual(res.status_code == 201, key in PIPELINE, (key, res.status_code))
        self.as_user(self.member2)
        self.assertEqual(self.client.post("/api/contracts/", {"lead": lead.pk}, format="json").status_code, 404)

    def test_each_action_has_one_owner(self):
        owners = {
            "start": ("requested", ("hr_head", "hr_member")), "send": ("drafting", ("hr_head", "hr_member")),
            "meeting": ("with_commercial", PIPELINE), "submit": ("meeting_logged", PIPELINE), "approve": ("ceo_review", ("ceo",)),
            "return": ("ceo_review", ("ceo",)), "handover": ("signed", ("hr_head", "hr_member")), "cancel": ("requested", ("commercial_head",)),
        }
        for name, (state, allowed) in owners.items():
            c = self.contract(state)
            for key in ALL_ROLES:
                self.as_role(key)
                res = self.client.post(f"/api/contracts/{c.pk}/{name}/", {"comment": "x", "reason": "x", "meeting_date": timezone.localdate().isoformat(), "meeting_notes": "n"}, format="json")
                if key not in allowed:
                    self.assertIn(res.status_code, (403, 404), (name, key, res.status_code))

    def test_flags(self):
        c = self.contract("ceo_review")
        self.as_role("ceo")
        self.assertTrue(self.client.get(f"/api/contracts/{c.pk}/").data["permissions"]["can_review"])
        self.as_role("hr_head")
        self.assertFalse(any(self.client.get(f"/api/contracts/{c.pk}/").data["permissions"].values()))

    def test_attach_rules_by_category(self):
        c = self.contract("drafting")
        self.assertTrue(self.hr2 and __import__("contracts.access", fromlist=["x"]).can_attach(self.hr2, c, "draft"))
        from contracts import access

        self.assertFalse(access.can_attach(self.member, c, "draft"))
        self.assertFalse(access.can_attach(self.member, c, "visit_report"))  # not with Commercial yet
        self.assertFalse(access.can_attach(self.hr, c, "final_signed"))
        self.assertFalse(access.can_attach(self.ceo, c, ""))
        done = self.contract("signed")
        self.assertTrue(access.can_attach(self.hr, done, "final_signed"))
        self.assertFalse(access.can_attach(self.member, done, "final_signed"))


class FlowTests(CCase):
    def test_request_needs_confirmed_or_skipped_quotation(self):
        open_lead = self.lead(skipped=False)
        self.as_role("commercial_head")
        self.assertEqual(self.client.post("/api/contracts/", {"lead": open_lead.pk}, format="json").data["detail"], services.MSG_NOT_READY)
        from quotations import services as qs

        q = qs.request_quotation(self.member, open_lead)
        self.assertEqual(self.client.post("/api/contracts/", {"lead": open_lead.pk}, format="json").status_code, 400)  # quotation still open
        Contract.objects.all().delete()
        from quotations.models import Quotation

        Quotation.objects.filter(pk=q.pk).update(status="confirmed", outcome_at=timezone.now())
        res = self.client.post("/api/contracts/", {"lead": open_lead.pk}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["quotation"], q.pk)

    def test_request_logs_notifies_and_rejects_bad_leads(self):
        c = self.contract()
        self.assertRegex(c.ref, r"^CT-\d{4}$")
        self.assertTrue(Notification.objects.filter(user=self.hr, kind="request_received", link=f"/contracts/{c.pk}").exists())
        self.assertEqual(self.actions(c)[:1], ["requested"])
        for lead in (self.lead(archived_at=timezone.now()), self.lead(status="new") if False else self.lead()):
            if lead.archived_at:
                self.as_role("commercial_head")
                self.assertEqual(self.client.post("/api/contracts/", {"lead": lead.pk}, format="json").status_code, 400)
        self.as_role("commercial_head")
        self.assertEqual(self.client.post("/api/contracts/", {"lead": c.lead_id}, format="json").data["detail"], services.MSG_OPEN_EXISTS)

    def test_one_open_contract_per_lead_in_database(self):
        c = self.contract()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Contract.objects.create(ref="CT-9999", lead=c.lead, requested_by=self.member)

    def test_cancel_frees_the_lead(self):
        c = self.contract()
        self.assertEqual(self.act(self.head, c, "cancel", {"reason": " "}).status_code, 400)
        res = self.act(self.head, c, "cancel", {"reason": "Client withdrew"})
        self.assertEqual((res.status_code, res.data["status"], res.data["cancel_reason"]), (200, "cancelled", "Client withdrew"))
        self.assertEqual(self.act(self.head, c, "cancel", {"reason": "again"}).status_code, 400)
        self.as_role("commercial_head")
        self.assertEqual(self.client.post("/api/contracts/", {"lead": c.lead_id}, format="json").status_code, 201)

    def test_cannot_cancel_after_handover(self):
        c = self.contract("handed_over")
        self.assertEqual(self.act(self.head, c, "cancel", {"reason": "x"}).status_code, 400)

    def test_draft_needs_a_file_each_round(self):
        c = self.contract("requested")
        self.assertEqual(self.act(self.hr, c, "send").data["detail"], services.MSG_STATE)
        self.act(self.hr, c, "start")
        self.assertEqual(self.act(self.hr, c, "send").data["detail"], services.MSG_NO_DRAFT)
        self.attach(c, "draft")
        res = self.act(self.hr, c, "send", {"note": "First draft"})
        self.assertEqual((res.status_code, res.data["status"]), (200, "with_commercial"))
        self.assertEqual([(v["number"], v["note"]) for v in res.data["versions"]], [(1, "First draft")])
        self.assertTrue(Notification.objects.filter(user=self.member, link=f"/contracts/{c.pk}").exists())

    def test_meeting_validation(self):
        c = self.contract("with_commercial")
        today = timezone.localdate()
        bad = [({}, "meeting_date"), ({"meeting_date": "soon", "meeting_notes": "n"}, "meeting_date"),
               ({"meeting_date": (today + timedelta(days=1)).isoformat(), "meeting_notes": "n"}, "meeting_date"),
               ({"meeting_date": today.isoformat(), "meeting_notes": " "}, "meeting_notes")]
        for body, field in bad:
            self.assertIn(field, self.act(self.member, c, "meeting", body).data, body)
        res = self.act(self.member, c, "meeting", {"meeting_date": today.isoformat(), "meeting_notes": "Agreed the terms"})
        self.assertEqual((res.status_code, res.data["status"], res.data["meeting_by_name"]), (200, "meeting_logged", self.member.full_name))

    def test_submit_needs_both_documents(self):
        c = self.contract("meeting_logged")
        self.assertEqual(self.act(self.member, c, "submit").data["detail"], services.MSG_NO_VISIT)
        self.attach(c, "visit_report", self.member)
        self.assertEqual(self.act(self.member, c, "submit").data["detail"], services.MSG_NO_SIGNED_COPY)
        att = self.attach(c, "client_signed_copy", self.member)
        att.archived_at = timezone.now()
        att.save()
        self.assertEqual(self.act(self.member, c, "submit").data["detail"], services.MSG_NO_SIGNED_COPY)  # archived files do not count
        self.attach(c, "client_signed_copy", self.member)
        res = self.act(self.member, c, "submit")
        self.assertEqual((res.status_code, res.data["status"]), (200, "ceo_review"))
        self.assertTrue(Notification.objects.filter(user=self.ceo, kind="contract_review").exists())

    def test_ceo_approves_and_signature_is_stored(self):
        c = self.contract("ceo_review")
        res = self.act(self.ceo, c, "approve")
        self.assertEqual((res.status_code, res.data["status"], res.data["signed_by_name"]), (200, "signed", self.ceo.full_name))
        self.assertIsNotNone(res.data["signed_at"])
        self.assertTrue(Notification.objects.filter(user=self.hr, kind="signed").exists())
        self.assertEqual(self.act(self.ceo, c, "approve").status_code, 400)

    def test_ceo_return_needs_comment_then_hr_can_redraft(self):
        c = self.contract("ceo_review")
        self.assertEqual(self.act(self.ceo, c, "return", {"comment": " "}).data["comment"], [services.MSG_COMMENT])
        res = self.act(self.ceo, c, "return", {"comment": "Fix clause 4"})
        self.assertEqual((res.status_code, res.data["status"], res.data["ceo_comment"]), (200, "returned", "Fix clause 4"))
        self.assertTrue(Notification.objects.filter(user=self.member, kind="returned").exists())
        self.assertEqual(self.act(self.hr, c, "start").data["status"], "drafting")
        self.assertEqual(self.act(self.hr, c, "send").data["detail"], services.MSG_NO_DRAFT)  # a new draft file is needed for the new version
        self.attach(c, "draft")
        res = self.act(self.hr, c, "send")
        self.assertEqual([v["number"] for v in res.data["versions"]], [1, 2])

    def test_returned_can_be_resubmitted_by_commercial_directly(self):
        c = self.contract("returned")
        self.act(self.member, c, "meeting", {"meeting_date": timezone.localdate().isoformat(), "meeting_notes": "Fixed with the client"})
        res = self.act(self.member, c, "submit")
        self.assertEqual((res.status_code, res.data["status"]), (200, "ceo_review"))
        self.assertEqual(res.data["ceo_comment"], "")

    def test_handover_needs_final_file_and_notifies_operation(self):
        c = self.contract("signed")
        self.assertEqual(self.act(self.hr, c, "handover").data["detail"], services.MSG_NO_FINAL)
        self.attach(c, "final_signed")
        res = self.act(self.hr2, c, "handover")
        self.assertEqual((res.status_code, res.data["status"], res.data["handed_over_by_name"]), (200, "handed_over", self.hr2.full_name))
        for key in ("operation_head", "operation_member"):
            self.assertTrue(Notification.objects.filter(user=self.users[key], kind="contract_handover").exists(), key)
        self.assertIn("contract_handed_over", list(AuditEntry.objects.filter(content_type=content_type_for(Lead), object_id=c.lead_id).values_list("action", flat=True)))

    def test_invalid_transitions_are_refused(self):
        for name, user, bad_states in [
            ("start", self.hr, ("drafting", "with_commercial", "meeting_logged", "ceo_review", "signed", "handed_over")),
            ("send", self.hr, ("requested", "with_commercial", "ceo_review", "signed")),
            ("submit", self.member, ("requested", "drafting", "with_commercial", "ceo_review", "signed")),
            ("approve", self.ceo, ("requested", "drafting", "with_commercial", "meeting_logged", "signed", "returned")),
            ("handover", self.hr, ("requested", "drafting", "ceo_review", "handed_over")),
        ]:
            for state in bad_states:
                c = self.contract(state)
                self.assertEqual(self.act(user, c, name).status_code, 400, (name, state))
        for state in ("requested", "drafting", "meeting_logged", "ceo_review", "signed"):
            c = self.contract(state)
            body = {"meeting_date": timezone.localdate().isoformat(), "meeting_notes": "n"}
            self.assertEqual(self.act(self.member, c, "meeting", body).status_code, 400, state)

    def test_full_audit_trail(self):
        c = self.contract("handed_over")
        self.assertEqual(self.actions(c), ["requested", "drafting_started", "sent_to_commercial", "meeting_logged", "submitted_to_ceo", "signed", "handed_over"])


class ListAndWorkTests(CCase):
    def test_filter_and_search(self):
        a, b = self.contract(), self.contract("ceo_review")
        self.as_role("ceo")
        ids = lambda q: {r["id"] for r in self.client.get(f"/api/contracts/{q}").data["results"]}
        self.assertEqual(ids("?status=ceo_review"), {b.pk})
        self.assertEqual(ids(f"?search={a.ref}"), {a.pk})
        self.assertEqual(ids("?open=1"), {a.pk, b.pk})

    def test_my_work(self):
        self.contract("requested")
        self.contract("drafting")
        self.contract("with_commercial")
        self.contract("meeting_logged")
        self.contract("ceo_review")
        self.contract("signed")
        self.contract("returned")

        def kinds(user):
            self.as_user(user)
            return sorted(i["kind"] for i in self.client.get("/api/my-work/").data["items"] if i["kind"].startswith("contract"))

        self.assertEqual(kinds(self.ceo), ["contract_review"])
        self.assertEqual(kinds(self.hr), ["contract_continue", "contract_draft", "contract_handover", "contract_redraft"])
        self.assertEqual(kinds(self.member), ["contract_meeting", "contract_meeting", "contract_submit"])
        self.assertEqual(kinds(self.member2), [])
        self.assertEqual(kinds(self.users["operation_head"]), [])

    def test_list_cost_does_not_grow(self):
        def cost():
            self.as_role("ceo")
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get("/api/contracts/?page_size=100").status_code, 200)
            return len(ctx)

        self.contract()
        few = cost()
        for _ in range(6):
            self.contract("signed")
        self.assertEqual(cost(), few)

    def test_lead_page_offers_contract_when_ready(self):
        lead = self.lead()
        self.as_role("commercial_member")
        p = self.client.get(f"/api/leads/{lead.pk}/").data
        self.assertTrue(p["permissions"]["can_request_contract"])
        self.assertIsNone(p["contract"])
        c = services.request_contract(self.member, lead)
        p = self.client.get(f"/api/leads/{lead.pk}/").data
        self.assertFalse(p["permissions"]["can_request_contract"])
        self.assertEqual(p["contract"], {"id": c.pk, "ref": c.ref, "status": "requested"})
        notready = self.lead(skipped=False)
        self.assertFalse(self.client.get(f"/api/leads/{notready.pk}/").data["permissions"]["can_request_contract"])
