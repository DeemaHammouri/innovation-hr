from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from audit.models import AuditEntry
from core.access import content_type_for
from core.roles import ALL_ROLES
from core.testing import RoleCase, png_signature
from leads.models import Lead
from lookups.models import RejectionReason, Service
from notifications.models import Notification
from quotations import reminders, services
from quotations.models import Quotation, QuotationLine, QuotationVersion


def line(**over):
    base = {"description": "Monthly bookkeeping", "quantity": "1", "unit_price": "100", "discount_percent": "0", "tax_percent": "0"}
    base.update(over)
    return base


class QCase(RoleCase):
    def setUp(self):
        super().setUp()
        self.mkt, self.head, self.member = self.users["marketing"], self.users["commercial_head"], self.users["commercial_member"]
        self.hr, self.hr2 = self.users["hr_head"], self.users["hr_member"]
        self.member2 = self.make_user("member2@x.com", "Commercial", "member")
        self.reason = RejectionReason.objects.filter(is_active=True).first()
        self.n = 0

    def lead(self, status="qualified", assigned=None, **kw):
        self.n += 1
        return Lead.objects.create(
            ref=f"LD-8{self.n:03d}", company_name=f"Client {self.n}", phone=f"07800000{self.n:02d}", created_by=self.mkt,
            status=status, assigned_to=assigned or self.member, assigned_at=timezone.now(), **kw,
        )

    def quote(self, state="requested", lead=None):
        """Walk a real quotation to `state` through the services, so the data is exactly what the workflow produces."""
        q = services.request_quotation(self.member, lead or self.lead(), "Please quote the monthly plan")
        if state == "requested":
            return Quotation.objects.get(pk=q.pk)
        q = services.start_preparing(self.hr, q)
        services.save_draft(self.hr, q, {"currency": "JOD", "valid_until": self.day(30), "lines": [line()]})
        if state != "in_preparation":
            q = services.submit(self.hr, q)
            if state == "changes_requested":
                q = services.request_changes(self.head, q, "Lower the price")
            elif state != "in_review":
                q = services.sign(self.head, q, png_signature())
                if state == "sent":
                    q = services.mark_sent(self.member, q)
        return Quotation.objects.get(pk=q.pk)

    def day(self, n):
        return (timezone.localdate() + timedelta(days=n)).isoformat()

    def actions(self, q):
        return list(AuditEntry.objects.filter(content_type=content_type_for(Quotation), object_id=q.pk).order_by("id").values_list("action", flat=True))

    def act(self, user, q, name, body=None, method="post"):
        self.as_user(user)
        return getattr(self.client, method)(f"/api/quotations/{q.pk}/{name}/", body or {}, format="json")


class AccessTests(QCase):
    def test_list_is_for_five_roles(self):
        self.assert_matrix("get", "/api/quotations/", {"ceo": 200, "commercial_head": 200, "commercial_member": 200, "hr_head": 200, "hr_member": 200, "*": 403})

    def test_create_is_for_the_head_and_the_assigned_member(self):
        lead = self.lead()
        for key in ALL_ROLES:
            Quotation.objects.all().delete()
            self.as_role(key)
            res = self.client.post("/api/quotations/", {"lead": lead.pk, "note": "x"}, format="json")
            expected = 201 if key in ("commercial_head", "commercial_member") else (404 if key == "marketing" else 403)
            # Marketing can see its own leads but the lead is not "theirs to quote"; the rest cannot see leads at all.
            self.assertIn(res.status_code, (expected, 404, 403), key)
            self.assertEqual(res.status_code == 201, key in ("commercial_head", "commercial_member"), key)

    def test_another_member_cannot_request_for_a_lead_that_is_not_theirs(self):
        lead = self.lead()
        self.as_user(self.member2)
        self.assertEqual(self.client.post("/api/quotations/", {"lead": lead.pk}, format="json").status_code, 404)

    def test_visibility(self):
        mine, theirs = self.quote(), self.quote(lead=self.lead(assigned=self.member2))
        self.as_role("commercial_member")
        self.assertEqual({r["id"] for r in self.client.get("/api/quotations/").data["results"]}, {mine.pk})
        self.assertEqual(self.client.get(f"/api/quotations/{theirs.pk}/").status_code, 404)
        for key in ("ceo", "commercial_head", "hr_head", "hr_member"):
            self.as_role(key)
            self.assertEqual(self.client.get("/api/quotations/").data["count"], 2, key)
        for key in ("marketing", "operation_head", "operation_member"):
            self.as_role(key)
            self.assertEqual(self.client.get(f"/api/quotations/{mine.pk}/").status_code, 403, key)

    def test_hr_actions_are_hr_only(self):
        q = self.quote()
        for key in ALL_ROLES:
            if key in ("hr_head", "hr_member"):
                continue
            self.as_role(key)
            for name, method in (("start", "post"), ("draft", "put"), ("submit", "post")):
                res = getattr(self.client, method)(f"/api/quotations/{q.pk}/{name}/", {}, format="json")
                self.assertIn(res.status_code, (403,), (key, name))

    def test_review_actions_are_head_only(self):
        q = self.quote("in_review")
        for key in ALL_ROLES:
            if key == "commercial_head":
                continue
            self.as_role(key)
            for name in ("sign", "request-changes", "cancel"):
                self.assertEqual(self.client.post(f"/api/quotations/{q.pk}/{name}/", {"comment": "x", "reason": "x"}, format="json").status_code, 403, (key, name))

    def test_send_and_outcome_need_the_pipeline(self):
        q = self.quote("signed")
        for key in ("ceo", "hr_head", "hr_member"):
            self.assertEqual(self.act(self.users[key], q, "send").status_code, 403, key)
        self.assertEqual(self.act(self.member2, q, "send").status_code, 404)
        self.assertEqual(self.act(self.member, q, "send").status_code, 200)
        for key in ("ceo", "hr_head"):
            self.assertEqual(self.act(self.users[key], q, "outcome", {"outcome": "confirmed"}).status_code, 403, key)

    def test_flags_tell_the_screen_what_is_allowed(self):
        q = self.quote("in_review")
        self.as_role("commercial_head")
        p = self.client.get(f"/api/quotations/{q.pk}/").data["permissions"]
        self.assertTrue(p["can_review"] and p["can_cancel"])
        self.assertFalse(p["can_edit"] or p["can_send"] or p["can_print"])
        self.as_role("hr_head")
        self.assertFalse(any(v for k, v in self.client.get(f"/api/quotations/{q.pk}/").data["permissions"].items()))
        self.as_role("ceo")
        self.assertFalse(any(self.client.get(f"/api/quotations/{q.pk}/").data["permissions"].values()))

    def test_comments_and_files_follow_the_quotation(self):
        q = self.quote()
        for key in ("marketing", "operation_head"):
            self.as_role(key)
            self.assertEqual(self.client.get(f"/api/comments/?target=quotation:{q.pk}").status_code, 404, key)
        for key in ("ceo", "hr_member", "commercial_head", "commercial_member"):
            self.as_role(key)
            self.assertEqual(self.client.get(f"/api/comments/?target=quotation:{q.pk}").status_code, 200, key)
        self.as_user(self.member2)
        self.assertEqual(self.client.get(f"/api/comments/?target=quotation:{q.pk}").status_code, 404)


class RequestTests(QCase):
    def test_request_creates_a_ref_notifies_hr_and_logs(self):
        lead = self.lead()
        self.as_role("commercial_member")
        res = self.client.post("/api/quotations/", {"lead": lead.pk, "note": "Quote the gold plan"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertRegex(res.data["ref"], r"^QT-\d{4}$")
        self.assertEqual((res.data["status"], res.data["request_note"]), ("requested", "Quote the gold plan"))
        for hr in (self.hr, self.hr2):
            self.assertTrue(Notification.objects.filter(user=hr, kind="request_received", link=f"/quotations/{res.data['id']}").exists())
        self.assertFalse(Notification.objects.filter(user=self.member, kind="request_received").exists())
        self.assertEqual(self.actions(Quotation.objects.get()), ["requested"])
        self.assertIn("quotation_requested", list(AuditEntry.objects.filter(content_type=content_type_for(Lead), object_id=lead.pk).values_list("action", flat=True)))

    def test_only_a_qualified_lead(self):
        for status in ("new", "contacted", "waiting", "rejected"):
            lead = self.lead(status=status)
            self.as_role("commercial_head")
            res = self.client.post("/api/quotations/", {"lead": lead.pk}, format="json")
            self.assertEqual(res.status_code, 400, status)
            self.assertEqual(res.data["detail"], services.MSG_NOT_QUALIFIED)

    def test_one_open_quotation_per_lead_but_a_new_one_after_rejection(self):
        lead = self.lead()
        q = services.request_quotation(self.member, lead)
        self.as_role("commercial_head")
        self.assertEqual(self.client.post("/api/quotations/", {"lead": lead.pk}, format="json").data["detail"], services.MSG_OPEN_EXISTS)
        self.act(self.head, q, "cancel", {"reason": "Wrong plan"})
        self.assertEqual(self.client.post("/api/quotations/", {"lead": lead.pk}, format="json").status_code, 201)

    def test_database_blocks_two_open_quotations(self):
        from django.db import IntegrityError, transaction

        lead = self.lead()
        services.request_quotation(self.member, lead)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Quotation.objects.create(ref="QT-9999", lead=lead, requested_by=self.member)

    def test_archived_lead_and_skipped_lead(self):
        archived = self.lead(archived_at=timezone.now())
        skipped = self.lead(skipped_quotation_at=timezone.now())
        self.as_role("commercial_head")
        self.assertEqual(self.client.post("/api/quotations/", {"lead": archived.pk}, format="json").data["detail"], services.MSG_LEAD_ARCHIVED)
        self.assertEqual(self.client.post("/api/quotations/", {"lead": skipped.pk}, format="json").data["detail"], services.MSG_SKIPPED)

    def test_bad_lead_ids(self):
        self.as_role("commercial_head")
        for bad in (None, "", "abc", 99999):
            self.assertEqual(self.client.post("/api/quotations/", {"lead": bad}, format="json").status_code, 404, bad)

    def test_skip_quotation(self):
        for key in ALL_ROLES:
            lead = self.lead()  # a fresh qualified lead for every role, assigned to the Commercial member
            self.as_role(key)
            res = self.client.post(f"/api/leads/{lead.pk}/skip-quotation/", {}, format="json")
            self.assertEqual(res.status_code, 200 if key in ("commercial_head", "commercial_member") else 403 if key in ("ceo", "marketing") else res.status_code, key)
            if key in ("commercial_head", "commercial_member"):
                lead.refresh_from_db()
                self.assertEqual(lead.skipped_quotation_by, self.users[key])
            else:
                self.assertIn(res.status_code, (403, 404), key)
        lead = self.lead()
        url = f"/api/leads/{lead.pk}/skip-quotation/"
        self.as_role("commercial_head")
        self.client.post(url, {}, format="json")
        self.assertEqual(self.client.post(url, {}, format="json").data["detail"], "The quotation was already skipped for this lead.")

    def test_skip_needs_a_qualified_lead_without_a_quotation(self):
        new = self.lead(status="new")
        self.as_role("commercial_head")
        self.assertEqual(self.client.post(f"/api/leads/{new.pk}/skip-quotation/", {}, format="json").status_code, 400)
        busy = self.lead()
        services.request_quotation(self.member, busy)
        self.assertEqual(self.client.post(f"/api/leads/{busy.pk}/skip-quotation/", {}, format="json").status_code, 400)

    def test_lead_page_knows_what_to_offer(self):
        lead = self.lead()
        self.as_role("commercial_member")
        p = self.client.get(f"/api/leads/{lead.pk}/").data
        self.assertTrue(p["permissions"]["can_request_quotation"] and p["permissions"]["can_skip_quotation"])
        self.assertIsNone(p["quotation"])
        q = services.request_quotation(self.member, lead)
        p = self.client.get(f"/api/leads/{lead.pk}/").data
        self.assertFalse(p["permissions"]["can_request_quotation"])
        self.assertEqual(p["quotation"], {"id": q.pk, "ref": q.ref, "status": "requested"})


class PreparationTests(QCase):
    def test_start_creates_an_empty_first_draft(self):
        q = self.quote()
        res = self.act(self.hr2, q, "start")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], "in_preparation")
        self.assertEqual([(v["number"], v["is_draft"]) for v in res.data["versions"]], [(1, True)])
        self.assertEqual(res.data["prepared_by_name"], self.hr2.full_name)
        self.assertEqual(self.act(self.hr, q, "start").status_code, 400)  # already started

    def test_save_draft_computes_totals_server_side(self):
        q = services.start_preparing(self.hr, self.quote())
        body = {
            "currency": "usd", "valid_until": self.day(14), "notes": "Payment within 30 days",
            "lines": [
                line(quantity="2", unit_price="100", discount_percent="10", tax_percent="16"),
                line(description="Setup", quantity="1", unit_price="50.555"),
            ],
        }
        res = self.act(self.hr, q, "draft", body, "put")
        self.assertEqual(res.status_code, 200, res.data)
        v = res.data["versions"][0]
        # line 1: 200 - 10% = 180, + 16% tax = 208.80. line 2: 50.56 (rounded half up)
        self.assertEqual([l["line_total"] for l in v["lines"]], ["208.80", "50.56"])
        self.assertEqual((v["subtotal"], v["discount_total"], v["tax_total"], v["total"]), ("250.56", "20.00", "28.80", "259.36"))
        self.assertEqual(v["currency"], "USD")

    def test_saving_again_replaces_the_lines(self):
        q = services.start_preparing(self.hr, self.quote())
        self.act(self.hr, q, "draft", {"valid_until": self.day(5), "lines": [line(), line(description="B")]}, "put")
        res = self.act(self.hr, q, "draft", {"valid_until": self.day(5), "lines": [line(description="Only")]}, "put")
        self.assertEqual([l["description"] for l in res.data["versions"][0]["lines"]], ["Only"])
        self.assertEqual(QuotationLine.objects.count(), 1)

    def test_a_line_service_can_be_linked(self):
        svc = Service.objects.filter(is_active=True).first()
        q = services.start_preparing(self.hr, self.quote())
        res = self.act(self.hr, q, "draft", {"valid_until": self.day(5), "lines": [line(service=svc.pk)]}, "put")
        self.assertEqual(res.data["versions"][0]["lines"][0]["service"], svc.pk)
        bad = self.act(self.hr, q, "draft", {"lines": [line(service=99999)]}, "put")
        self.assertEqual(bad.data["lines"][0]["service"], services.MSG_SERVICE)

    def test_line_validation_names_the_line_and_the_field(self):
        q = services.start_preparing(self.hr, self.quote())
        res = self.act(self.hr, q, "draft", {"lines": [line(), line(description=" ", quantity="0", unit_price="-1", discount_percent="101", tax_percent="abc")]}, "put")
        self.assertEqual(res.status_code, 400)
        errors = res.data["lines"]
        self.assertEqual(errors[0], {})
        self.assertEqual(errors[1]["description"], services.MSG_DESCRIPTION)
        self.assertEqual(errors[1]["quantity"], services.MSG_QUANTITY)
        self.assertEqual(errors[1]["unit_price"], services.MSG_PRICE)
        self.assertEqual(errors[1]["discount_percent"], services.MSG_PERCENT)
        self.assertEqual(errors[1]["tax_percent"], services.MSG_NUMBER)

    def test_a_refused_save_changes_nothing(self):
        q = services.start_preparing(self.hr, self.quote())
        self.act(self.hr, q, "draft", {"valid_until": self.day(5), "lines": [line(description="Keep me")]}, "put")
        self.act(self.hr, q, "draft", {"lines": [line(description="")]}, "put")
        self.assertEqual(list(QuotationLine.objects.values_list("description", flat=True)), ["Keep me"])

    def test_other_validation(self):
        q = services.start_preparing(self.hr, self.quote())
        self.assertIn("currency", self.act(self.hr, q, "draft", {"currency": "JORDAN"}, "put").data)
        self.assertIn("valid_until", self.act(self.hr, q, "draft", {"valid_until": "soon"}, "put").data)
        self.assertIn("lines", self.act(self.hr, q, "draft", {"lines": [line()] * 101}, "put").data)
        self.assertIn("notes", self.act(self.hr, q, "draft", {"notes": "x" * 2001}, "put").data)
        for huge in ("1e400", "NaN", "Infinity"):
            self.assertEqual(self.act(self.hr, q, "draft", {"lines": [line(unit_price=huge)]}, "put").status_code, 400, huge)

    def test_draft_only_while_in_preparation(self):
        q = self.quote("in_review")
        self.assertEqual(self.act(self.hr, q, "draft", {"lines": [line()]}, "put").data["detail"], services.MSG_STATE)
        fresh = self.quote()
        self.assertEqual(self.act(self.hr, fresh, "draft", {"lines": [line()]}, "put").data["detail"], services.MSG_STATE)

    def test_submit_needs_lines_and_a_valid_date(self):
        q = services.start_preparing(self.hr, self.quote())
        self.assertEqual(self.act(self.hr, q, "submit").data["lines"], [services.MSG_NO_LINES])
        self.act(self.hr, q, "draft", {"lines": [line()]}, "put")
        self.assertEqual(self.act(self.hr, q, "submit").data["valid_until"], [services.MSG_VALID_UNTIL])
        self.act(self.hr, q, "draft", {"valid_until": self.day(-1), "lines": [line()]}, "put")
        self.assertEqual(self.act(self.hr, q, "submit").data["valid_until"], [services.MSG_VALID_PAST])
        self.act(self.hr, q, "draft", {"valid_until": self.day(10), "lines": [line()]}, "put")
        res = self.act(self.hr, q, "submit")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], "in_review")
        self.assertFalse(res.data["versions"][0]["is_draft"])
        self.assertTrue(Notification.objects.filter(user=self.head, kind="quotation_review").exists())

    def test_a_submitted_version_is_frozen(self):
        q = self.quote("in_review")
        self.assertEqual(self.act(self.hr, q, "draft", {"lines": [line(description="Sneaky")]}, "put").status_code, 400)
        self.assertEqual(QuotationLine.objects.get().description, "Monthly bookkeeping")


class ReviewTests(QCase):
    def test_changes_need_a_comment_then_a_new_version_copies_the_last(self):
        q = self.quote("in_review")
        self.assertEqual(self.act(self.head, q, "request-changes", {"comment": " "}).data["comment"], [services.MSG_COMMENT])
        res = self.act(self.head, q, "request-changes", {"comment": "Lower the price"})
        self.assertEqual((res.status_code, res.data["status"], res.data["review_comment"]), (200, "changes_requested", "Lower the price"))
        self.assertTrue(Notification.objects.filter(user=self.hr, kind="returned").exists())
        again = self.act(self.hr2, q, "start")
        self.assertEqual(again.status_code, 200, again.data)
        v1, v2 = again.data["versions"]
        self.assertEqual((v1["number"], v1["is_draft"], v2["number"], v2["is_draft"]), (1, False, 2, True))
        self.assertEqual([l["description"] for l in v2["lines"]], [l["description"] for l in v1["lines"]])
        self.assertEqual(v2["total"], v1["total"])
        # editing version 2 does not touch version 1
        self.act(self.hr2, q, "draft", {"valid_until": self.day(20), "lines": [line(unit_price="80")]}, "put")
        q.refresh_from_db()
        self.assertEqual(QuotationVersion.objects.get(quotation=q, number=1).total, Decimal("100.00"))
        self.assertEqual(QuotationVersion.objects.get(quotation=q, number=2).total, Decimal("80.00"))
        self.assertEqual(self.actions(q), ["requested", "preparation_started", "submitted", "changes_requested", "version_started"])

    def test_sign_stores_signer_time_and_version(self):
        q = self.quote("in_review")
        res = self.act(self.head, q, "sign", {"signature": png_signature()})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data["status"], res.data["signed_by_name"], res.data["signed_version"]), ("signed", self.head.full_name, 1))
        self.assertIsNotNone(res.data["signed_at"])
        self.assertTrue(res.data["permissions"]["can_print"])
        self.assertTrue(Notification.objects.filter(user=self.hr, kind="signed").exists())
        self.assertTrue(Notification.objects.filter(user=self.member, kind="signed").exists())
        self.assertFalse(Notification.objects.filter(user=self.head, kind="signed").exists())

    def test_the_ceo_cannot_sign(self):
        q = self.quote("in_review")
        self.assertEqual(self.act(self.users["ceo"], q, "sign", {"signature": png_signature()}).status_code, 403)

    def test_sign_only_from_in_review(self):
        for state in ("requested", "in_preparation", "changes_requested", "signed", "sent"):
            q = self.quote(state)
            self.assertEqual(self.act(self.head, q, "sign", {"signature": png_signature()}).status_code, 400, state)

    def test_cannot_request_changes_after_signing(self):
        q = self.quote("signed")
        self.assertEqual(self.act(self.head, q, "request-changes", {"comment": "no"}).status_code, 400)

    def test_cancel(self):
        for state in ("requested", "in_preparation", "in_review", "changes_requested", "signed", "sent"):
            q = self.quote(state)
            self.assertEqual(self.act(self.head, q, "cancel", {"reason": " "}).status_code, 400, state)
            res = self.act(self.head, q, "cancel", {"reason": "Client changed plans"})
            self.assertEqual((res.status_code, res.data["status"], res.data["cancel_reason"]), (200, "cancelled", "Client changed plans"), state)
            self.assertEqual(self.act(self.head, q, "cancel", {"reason": "again"}).status_code, 400, state)
        self.assertEqual(Quotation.objects.count(), 6)  # cancelled, never deleted


class OutcomeTests(QCase):
    def outcome(self, q, **body):
        return self.act(self.member, q, "outcome", body)

    def test_send_then_each_outcome(self):
        q = self.quote("signed")
        res = self.act(self.member, q, "send")
        self.assertEqual((res.status_code, res.data["status"]), (200, "sent"))
        self.assertIsNotNone(res.data["sent_at"])
        self.assertEqual(self.act(self.member, q, "send").status_code, 400)
        self.assertEqual(self.outcome(q, outcome="confirmed").data["status"], "confirmed")

    def test_send_only_when_signed(self):
        for state in ("requested", "in_preparation", "in_review", "changes_requested"):
            self.assertEqual(self.act(self.member, self.quote(state), "send").status_code, 400, state)

    def test_waiting_needs_a_date_and_can_repeat_then_resolve(self):
        q = self.quote("sent")
        self.assertEqual(self.outcome(q, outcome="waiting").data["next_follow_up"], [services.MSG_FOLLOW_UP])
        self.assertEqual(self.outcome(q, outcome="waiting", next_follow_up=self.day(-1)).data["next_follow_up"], [services.MSG_FOLLOW_UP_PAST])
        self.assertEqual(self.outcome(q, outcome="waiting", next_follow_up=self.day(400)).data["next_follow_up"], [services.MSG_FOLLOW_UP_FAR])
        self.assertEqual(self.outcome(q, outcome="waiting", next_follow_up="tomorrow").status_code, 400)
        self.assertEqual(self.outcome(q, outcome="waiting", next_follow_up=self.day(7)).data["status"], "waiting")
        self.assertEqual(self.outcome(q, outcome="waiting", next_follow_up=self.day(14)).data["next_follow_up"], self.day(14))
        res = self.outcome(q, outcome="confirmed")
        self.assertEqual((res.data["status"], res.data["next_follow_up"]), ("confirmed", None))

    def test_rejected_needs_an_active_reason(self):
        q = self.quote("sent")
        self.assertIn("rejection_reason", self.outcome(q, outcome="rejected").data)
        self.assertIn("rejection_reason", self.outcome(q, outcome="rejected", rejection_reason=99999).data)
        res = self.outcome(q, outcome="rejected", rejection_reason=self.reason.pk, rejection_note="Too expensive")
        self.assertEqual((res.status_code, res.data["status"], res.data["rejection_note"]), (200, "rejected", "Too expensive"))
        self.assertTrue(Notification.objects.filter(user=self.head, kind="quotation_rejected").exists())
        self.assertTrue(Notification.objects.filter(user=self.hr, kind="quotation_rejected").exists())

    def test_outcomes_only_after_sending_and_never_twice(self):
        for state in ("requested", "in_review", "signed"):
            self.assertEqual(self.outcome(self.quote(state), outcome="confirmed").status_code, 400, state)
        q = self.quote("sent")
        self.outcome(q, outcome="confirmed")
        self.assertEqual(self.outcome(q, outcome="rejected", rejection_reason=self.reason.pk).status_code, 400)
        self.assertEqual(self.outcome(self.quote("sent"), outcome="maybe").status_code, 400)

    def test_head_hears_about_confirmation_from_a_member_but_not_their_own(self):
        q = self.quote("sent")
        self.outcome(q, outcome="confirmed")
        self.assertTrue(Notification.objects.filter(user=self.head, kind="quotation_confirmed").exists())
        q2 = self.quote("sent", lead=self.lead(assigned=self.head))
        self.act(self.head, q2, "outcome", {"outcome": "confirmed"})
        self.assertEqual(Notification.objects.filter(user=self.head, kind="quotation_confirmed").count(), 1)

    def test_rejected_frees_the_lead_for_another_quotation(self):
        q = self.quote("sent")
        self.outcome(q, outcome="rejected", rejection_reason=self.reason.pk)
        self.as_role("commercial_head")
        self.assertEqual(self.client.post("/api/quotations/", {"lead": q.lead_id}, format="json").status_code, 201)

    def test_full_audit_trail(self):
        q = self.quote("sent")
        self.outcome(q, outcome="waiting", next_follow_up=self.day(3))
        self.outcome(q, outcome="confirmed")
        self.assertEqual(self.actions(q), ["requested", "preparation_started", "submitted", "signed", "sent", "outcome_waiting", "outcome_confirmed"])
        self.as_role("hr_member")
        timeline = self.client.get(f"/api/activity/?target=quotation:{q.pk}").data["results"]
        self.assertEqual(timeline[0]["action"], "outcome_confirmed")


class ListMyWorkAndReminderTests(QCase):
    def test_filters_and_search(self):
        a, b = self.quote(), self.quote("signed")
        self.as_role("commercial_head")
        ids = lambda q: {r["id"] for r in self.client.get(f"/api/quotations/{q}").data["results"]}
        self.assertEqual(ids("?status=signed"), {b.pk})
        self.assertEqual(ids("?status=requested,signed"), {a.pk, b.pk})
        self.assertEqual(ids(f"?search={a.ref}"), {a.pk})
        self.assertEqual(ids(f"?search={b.lead.company_name}"), {b.pk})
        self.assertEqual(ids(f"?lead={a.lead_id}"), {a.pk})
        self.assertEqual(ids("?open=1"), {a.pk, b.pk})

    def test_list_rows_carry_the_total_of_the_signed_version(self):
        q = self.quote("signed")
        self.as_role("commercial_head")
        row = self.client.get("/api/quotations/").data["results"][0]
        self.assertEqual((row["latest"]["total"], row["latest"]["currency"], row["latest"]["number"]), ("100.00", "JOD", 1))
        self.assertNotIn("versions", row)

    def test_overdue_filter_and_flag(self):
        q = self.quote("sent")
        services.set_outcome(self.member, q, outcome="waiting", next_follow_up=timezone.localdate())
        Quotation.objects.filter(pk=q.pk).update(next_follow_up=timezone.localdate() - timedelta(days=2))
        self.as_role("commercial_head")
        self.assertEqual(self.client.get("/api/quotations/?overdue=1").data["count"], 1)
        self.assertTrue(self.client.get("/api/quotations/").data["results"][0]["follow_up_overdue"])

    def test_my_work_by_role(self):
        self.quote()                      # requested -> HR prepares
        self.quote("in_preparation")      # HR continues
        self.quote("changes_requested")   # HR revises
        self.quote("in_review")           # head signs
        self.quote("signed")              # pipeline sends
        self.quote("sent")                # pipeline records outcome
        def kinds(user):
            self.as_user(user)
            return sorted(i["kind"] for i in self.client.get("/api/my-work/").data["items"] if i["kind"].startswith("quotation"))
        self.assertEqual(kinds(self.hr), ["quotation_changes", "quotation_continue", "quotation_prepare"])
        self.assertEqual(kinds(self.head), ["quotation_outcome", "quotation_send", "quotation_sign"])
        self.assertEqual(kinds(self.member), ["quotation_outcome", "quotation_send"])
        self.assertEqual(kinds(self.member2), [])
        self.assertEqual(kinds(self.users["ceo"]), [])

    def test_reminders_fire_once_per_date(self):
        q = self.quote("sent")
        services.set_outcome(self.member, q, outcome="waiting", next_follow_up=timezone.localdate())
        Quotation.objects.filter(pk=q.pk).update(next_follow_up=timezone.localdate() - timedelta(days=1))
        self.assertEqual(reminders.run(), 1)
        self.assertEqual(reminders.run(), 0)
        self.assertTrue(Notification.objects.filter(user=self.member, kind="followup_overdue", link=f"/quotations/{q.pk}").exists())
        Quotation.objects.filter(pk=q.pk).update(next_follow_up=timezone.localdate() - timedelta(days=4))
        self.assertEqual(reminders.run(), 1)

    def test_list_cost_does_not_grow(self):
        def cost():
            self.as_role("commercial_head")
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get("/api/quotations/?page_size=100").status_code, 200)
            return len(ctx)

        self.quote("signed")
        few = cost()
        for _ in range(8):
            self.quote("sent")
        self.assertEqual(cost(), few)

    def test_detail_cost_is_bounded(self):
        q = self.quote("changes_requested")
        services.start_preparing(self.hr, q)
        self.as_role("commercial_head")
        with CaptureQueriesContext(connection) as ctx:
            self.assertEqual(self.client.get(f"/api/quotations/{q.pk}/").status_code, 200)
        self.assertLessEqual(len(ctx), 16)

    def test_money_constraints_live_in_the_database(self):
        from django.db import IntegrityError, transaction

        q = services.start_preparing(self.hr, self.quote())
        v = q.versions.get()
        for bad in ({"quantity": 0}, {"unit_price": -1}, {"discount_percent": 101}, {"tax_percent": -1}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                QuotationLine.objects.create(version=v, description="x", **{"quantity": 1, "unit_price": 1, **bad})
