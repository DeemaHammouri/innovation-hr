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
        from core.testing import ensure_stamp, png_signature

        ensure_stamp()
        c = services.request_contract(self.member, lead or self.lead(), "Standard terms")
        if state == "requested":
            return Contract.objects.get(pk=c.pk)
        path = {
            "drafting": 1, "with_commercial": 2, "returned_commercial": 2, "confirmed": 3, "sent": 4, "ceo_review": 5, "returned": 5, "signed": 6, "handed_over": 7,
        }[state]
        c = services.start_drafting(self.hr, c)
        if path >= 2:
            c = services.send_to_commercial(self.hr, c)
        if state == "returned_commercial":
            c = services.return_to_hr(self.head, c, "Fix clause 4")
        if path >= 3 and state != "returned_commercial":
            c = services.confirm(self.head, c)
        if path >= 4:
            c = services.send_to_client(self.hr, c)
        if path >= 5:
            c = self._client_signs(c)
        if state == "returned":
            c = services.ceo_return(self.ceo, c, "Fix clause 4")
        if path >= 6 and state != "returned":
            c = services.ceo_sign(self.ceo, c, png_signature())
        if path >= 7:
            c = services.hand_over(self.hr, c)
        return Contract.objects.get(pk=c.pk)

    def _client_signs(self, c):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return services.upload_client_copy(self.member, c, SimpleUploadedFile("c.pdf", b"%PDF-1.4 signed", "application/pdf"))

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
            "confirm": ("with_commercial", ("commercial_head",)), "commercial-return": ("with_commercial", ("commercial_head",)),
            "send-to-client": ("confirmed", ("hr_head", "hr_member")), "approve": ("ceo_review", ("ceo",)),
            "return": ("ceo_review", ("ceo",)), "handover": ("signed", ("hr_head", "hr_member")), "cancel": ("requested", ("commercial_head",)),
        }
        for name, (state, allowed) in owners.items():
            c = self.contract(state)
            for key in ALL_ROLES:
                self.as_role(key)
                if key in allowed:
                    continue  # the allowed person would change the state; they are covered by the flow tests
                res = self.client.post(f"/api/contracts/{c.pk}/{name}/", {"comment": "x", "reason": "x", "signature": "x"}, format="json")
                self.assertIn(res.status_code, (403, 404), (name, key, res.status_code))
                self.assertEqual(Contract.objects.get(pk=c.pk).status, state, (name, key))

    def test_flags(self):
        c = self.contract("ceo_review")
        self.as_role("ceo")
        self.assertTrue(self.client.get(f"/api/contracts/{c.pk}/").data["permissions"]["can_review"])
        self.as_role("hr_head")
        self.assertFalse(any(self.client.get(f"/api/contracts/{c.pk}/").data["permissions"].values()))

    def test_attach_rules_by_category(self):
        from contracts import access

        c = self.contract("drafting")
        self.assertTrue(access.can_attach(self.hr2, c, "draft"))
        self.assertFalse(access.can_attach(self.member, c, "draft"))
        self.assertFalse(access.can_attach(self.member, c, "client_signed_copy"))  # not sent to the client yet
        self.assertFalse(access.can_attach(self.hr, c, "final_signed"))
        self.assertFalse(access.can_attach(self.ceo, c, ""))
        sent = self.contract("sent")
        self.assertTrue(access.can_attach(self.member, sent, "client_signed_copy"))
        self.assertTrue(access.can_attach(self.hr, sent, "client_signed_copy"))
        review = self.contract("ceo_review")
        self.assertTrue(access.can_attach(self.ceo, review, "final_signed"))
        self.assertFalse(access.can_attach(self.member, review, "final_signed"))


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

    def test_prefilled_from_the_signed_quotation_and_the_country_template(self):
        from quotations.models import Quotation, QuotationLine, QuotationVersion

        lead = self.lead(skipped=False)
        q = Quotation.objects.create(ref="QT-0099", lead=lead, requested_by=self.member, status="confirmed", outcome_at=timezone.now(), number="QT/2026/11/0001")
        v = QuotationVersion.objects.create(quotation=q, number=1, currency="SAR", payment_terms="50% now, 50% on delivery", created_by=self.hr, total="1500.00")
        QuotationLine.objects.create(version=v, description="Monthly bookkeeping", quantity=1, unit_price="1500.00", line_total="1500.00", frequency="monthly", visits=2)
        c = services.request_contract(self.member, lead)
        ver = c.versions.get()
        self.assertEqual((ver.currency, str(ver.total), ver.payment_terms), ("SAR", "1500.00", "50% now, 50% on delivery"))
        self.assertEqual(ver.services[0]["description"], "Monthly bookkeeping")
        self.assertIn(lead.company_name, ver.body_en)
        self.assertIn("1,500.00", ver.body_en)
        self.assertIn("SAR", ver.body_ar)
        self.assertNotIn("{", ver.body_en)

    def test_the_clients_country_picks_the_template(self):
        from clients.models import Client
        from contracts.models import ContractTemplate

        ContractTemplate.objects.create(country="SA", name_en="Saudi", name_ar="سعودي", body_en="SAUDI CONTRACT for {client}", body_ar="عقد سعودي لـ {client}")
        lead = self.lead()
        Client.objects.create(lead=lead, company_name=lead.company_name, country="SA", created_by=self.head, status="prospect")
        c = services.request_contract(self.member, lead)
        self.assertEqual(c.country, "SA")
        self.assertEqual(c.versions.get().body_en, f"SAUDI CONTRACT for {lead.company_name}")
        c2 = services.request_contract(self.member, self.lead())  # no client, default JO: falls back to the standard template
        self.assertIn("SERVICES AGREEMENT", c2.versions.get().body_en)

    def test_hr_edits_the_draft_and_it_needs_text_to_be_sent(self):
        c = self.contract("requested")
        self.assertEqual(self.act(self.hr, c, "send").data["detail"], services.MSG_STATE)
        self.act(self.hr, c, "start")
        self.act(self.hr, c, "draft", {"body_en": "", "body_ar": " "})
        self.assertEqual(self.act(self.hr, c, "send").data["detail"], services.MSG_NO_DRAFT)
        res = self.act(self.hr, c, "draft", {"title": "Bookkeeping", "body_en": "Clause 1", "end_date": "2027-01-01", "start_date": "2026-01-01"})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.act(self.hr, c, "draft", {"start_date": "2026-05-01", "end_date": "2026-01-01"}).status_code, 400)
        self.assertEqual(self.act(self.hr, c, "draft", {"currency": "dollars"}).status_code, 400)
        self.assertEqual(self.act(self.member, c, "draft", {"body_en": "x"}).status_code, 403)
        res = self.act(self.hr, c, "send", {"note": "First draft"})
        self.assertEqual((res.status_code, res.data["status"]), (200, "with_commercial"))
        self.assertEqual([(v["number"], v["note"]) for v in res.data["versions"]], [(1, "First draft")])
        self.assertEqual(self.act(self.hr, c, "draft", {"body_en": "late"}).status_code, 400)  # locked once with Commercial
        self.assertTrue(Notification.objects.filter(user=self.member, link=f"/contracts/{c.pk}").exists())

    def test_commercial_returns_with_notes_and_hr_redrafts_a_new_version(self):
        c = self.contract("with_commercial")
        self.assertEqual(self.act(self.head, c, "commercial-return", {"comment": " "}).data["comment"], [services.MSG_COMMENT])
        res = self.act(self.head, c, "commercial-return", {"comment": "Fix clause 4"})
        self.assertEqual((res.status_code, res.data["status"], res.data["returned_comment"]), (200, "returned", "Fix clause 4"))
        self.assertTrue(Notification.objects.filter(user=self.hr, kind="returned").exists())
        self.assertEqual(self.act(self.hr, c, "start").data["status"], "drafting")
        self.act(self.hr, c, "draft", {"body_en": "Clause 4 fixed"})
        res = self.act(self.hr, c, "send")
        self.assertEqual([v["number"] for v in res.data["versions"]], [1, 2])
        self.assertEqual(res.data["returned_comment"], "")
        self.assertEqual(c.versions.get(number=2).body_en, "Clause 4 fixed")

    def test_a_member_cannot_confirm(self):
        c = self.contract("with_commercial")
        self.assertEqual(self.act(self.member, c, "confirm").status_code, 403)

    def test_confirm_then_send_issues_the_contracts_own_number(self):
        from core.models import CompanyProfile

        CompanyProfile.objects.update_or_create(pk=1, defaults={"contract_prefix": "AGR"})
        c = self.contract("confirmed")
        self.assertIsNone(c.number)
        res = self.act(self.hr, c, "send-to-client")
        today = timezone.localdate()
        self.assertEqual((res.status_code, res.data["status"], res.data["number"]), (200, "sent", f"AGR/{today.year}/{today.month}/0001"))
        d = self.contract("confirmed")
        self.assertEqual(self.act(self.hr, d, "send-to-client").data["number"], f"AGR/{today.year}/{today.month}/0002")
        self.assertEqual(self.act(self.hr, c, "send-to-client").status_code, 400)  # never a second number
        self.assertEqual(Contract.objects.get(pk=c.pk).number, f"AGR/{today.year}/{today.month}/0001")

    def test_numbers_have_no_gaps_or_duplicates(self):
        from core.models import YearSequence

        numbers = [self.act(self.hr, self.contract("confirmed"), "send-to-client").data["number"] for _ in range(5)]
        self.assertEqual([int(n.rsplit("/", 1)[1]) for n in numbers], [1, 2, 3, 4, 5])
        self.assertEqual(len(set(numbers)), 5)
        self.assertEqual(YearSequence.objects.get(key="contract").last, 5)

    def test_client_signs_on_the_portal_then_the_ceo_signs_with_signature_and_stamp(self):
        from accounts.models import User
        from clients import services as client_services
        from clients.models import Client
        from core.testing import png_signature

        c = self.contract("sent")
        client = Client.objects.create(lead=c.lead, company_name=c.lead.company_name, email="cl@client.example", status="prospect", created_by=self.head)
        client_services.create_portal_account(client, self.head)
        client.refresh_from_db()
        User.objects.filter(pk=client.portal_user_id).update(must_change_password=False)
        self.as_user(client.portal_user)
        self.assertEqual(self.client.post(f"/api/portal/contracts/{c.pk}/sign/", {"signature": png_signature(blank=True)}, format="json").status_code, 400)
        res = self.client.post(f"/api/portal/contracts/{c.pk}/sign/", {"signature": png_signature()}, format="json")
        self.assertEqual((res.status_code, res.data["status"]), (200, "ceo_review"))
        self.assertEqual(self.client.post(f"/api/portal/contracts/{c.pk}/sign/", {"signature": png_signature()}, format="json").status_code, 400)  # only once
        self.assertTrue(Notification.objects.filter(user=self.ceo, kind="contract_review").exists())
        self.assertEqual(self.act(self.head, c, "approve", {"signature": png_signature()}).status_code, 403)  # not the Commercial head's step
        self.assertEqual(self.act(self.ceo, c, "approve", {}).status_code, 400)  # nothing drawn and nothing uploaded
        res = self.act(self.ceo, c, "approve", {"signature": png_signature()})
        self.assertEqual((res.status_code, res.data["status"], res.data["signed_by_name"], res.data["signed_via"]), (200, "signed", self.ceo.full_name, "drawn"))
        stored = Contract.objects.get(pk=c.pk)
        self.assertTrue(stored.signature and stored.stamp and stored.client_signature)
        self.assertEqual(self.act(self.ceo, c, "approve", {"signature": png_signature()}).status_code, 400)
        self.assertEqual(self.act(self.hr, c, "handover").data["status"], "handed_over")  # a drawn signature is the final copy

    def test_ceo_needs_a_stamp_for_a_drawn_signature(self):
        from core.models import CompanyProfile
        from core.testing import png_signature

        c = self.contract("ceo_review")
        profile = CompanyProfile.get()
        profile.stamp = ""
        profile.save()
        res = self.act(self.ceo, c, "approve", {"signature": png_signature()})
        self.assertEqual((res.status_code, services.MSG_STAMP in str(res.data)), (400, True))

    def test_ceo_can_upload_the_final_copy_instead(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        c = self.contract("ceo_review")
        self.as_user(self.ceo)
        bad = self.client.post(f"/api/contracts/{c.pk}/approve/", {"file": SimpleUploadedFile("x.exe", b"MZ", "application/octet-stream")}, format="multipart")
        self.assertEqual(bad.status_code, 400)
        res = self.client.post(f"/api/contracts/{c.pk}/approve/", {"file": SimpleUploadedFile("final.pdf", b"%PDF-1.4 final", "application/pdf")}, format="multipart")
        self.assertEqual((res.status_code, res.data["signed_via"]), (200, "upload"))
        self.assertTrue(Attachment.objects.filter(object_id=c.pk, category="final_signed").exists())
        self.assertEqual(self.act(self.hr, c, "handover").data["status"], "handed_over")

    def test_ceo_return_needs_comment_then_hr_can_redraft(self):
        c = self.contract("ceo_review")
        self.assertEqual(self.act(self.ceo, c, "return", {"comment": " "}).data["comment"], [services.MSG_COMMENT])
        res = self.act(self.ceo, c, "return", {"comment": "Fix clause 4"})
        self.assertEqual((res.status_code, res.data["status"], res.data["ceo_comment"]), (200, "returned", "Fix clause 4"))
        self.assertTrue(Notification.objects.filter(user=self.member, kind="returned").exists())
        self.assertEqual(self.act(self.hr, c, "start").data["status"], "drafting")

    def test_staff_upload_the_clients_signed_copy(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        c = self.contract("sent")
        self.as_user(self.users["operation_head"])
        self.assertIn(self.client.post(f"/api/contracts/{c.pk}/client-copy/", {}, format="multipart").status_code, (403, 404))
        self.as_user(self.member)
        self.assertEqual(self.client.post(f"/api/contracts/{c.pk}/client-copy/", {}, format="multipart").status_code, 400)
        res = self.client.post(f"/api/contracts/{c.pk}/client-copy/", {"file": SimpleUploadedFile("signed.pdf", b"%PDF-1.4 signed", "application/pdf")}, format="multipart")
        self.assertEqual((res.status_code, res.data["status"], res.data["client_signed_via"]), (200, "ceo_review", "upload"))

    def test_handover_after_an_uploaded_final_copy_needs_the_file(self):
        c = self.contract("signed")
        Contract.objects.filter(pk=c.pk).update(signed_via="upload")
        self.assertEqual(self.act(self.hr, c, "handover").data["detail"], services.MSG_NO_FINAL)
        self.attach(c, "final_signed")
        res = self.act(self.hr2, c, "handover")
        self.assertEqual((res.status_code, res.data["status"], res.data["handed_over_by_name"]), (200, "handed_over", self.hr2.full_name))
        for key in ("operation_head", "operation_member"):
            self.assertTrue(Notification.objects.filter(user=self.users[key], kind="contract_handover").exists(), key)
        self.assertIn("contract_handed_over", list(AuditEntry.objects.filter(content_type=content_type_for(Lead), object_id=c.lead_id).values_list("action", flat=True)))

    def test_every_illegal_transition_is_refused(self):
        from core.testing import png_signature

        legal = {
            "start": {"requested", "returned"}, "send": {"drafting"}, "confirm": {"with_commercial"}, "commercial-return": {"with_commercial"},
            "send-to-client": {"confirmed"}, "approve": {"ceo_review"}, "return": {"ceo_review"}, "handover": {"signed"},
        }
        actors = {"start": self.hr, "send": self.hr, "confirm": self.head, "commercial-return": self.head, "send-to-client": self.hr, "approve": self.ceo, "return": self.ceo, "handover": self.hr}
        for name, ok in legal.items():
            for state in ("requested", "drafting", "with_commercial", "confirmed", "sent", "ceo_review", "returned", "signed", "handed_over"):
                if state in ok:
                    continue
                c = self.contract(state)
                res = self.act(actors[name], c, name, {"comment": "x", "signature": png_signature()})
                self.assertEqual(res.status_code, 400, (name, state, res.status_code))
                self.assertEqual(Contract.objects.get(pk=c.pk).status, state, (name, state))

    def test_full_audit_trail(self):
        c = self.contract("handed_over")
        self.assertEqual(self.actions(c), ["requested", "drafting_started", "sent_to_commercial", "confirmed", "sent", "client_signed", "signed", "handed_over"])


class ListAndWorkTests(CCase):
    def test_filter_and_search(self):
        a, b = self.contract(), self.contract("ceo_review")
        self.as_role("ceo")
        ids = lambda q: {r["id"] for r in self.client.get(f"/api/contracts/{q}").data["results"]}
        self.assertEqual(ids("?status=ceo_review"), {b.pk})
        self.assertEqual(ids(f"?search={a.ref}"), {a.pk})
        self.assertEqual(ids("?open=1"), {a.pk, b.pk})

    def test_my_work(self):
        for state in ("requested", "drafting", "with_commercial", "confirmed", "ceo_review", "signed", "returned"):
            self.contract(state)

        def kinds(user):
            self.as_user(user)
            return sorted(i["kind"] for i in self.client.get("/api/my-work/").data["items"] if i["kind"].startswith("contract"))

        self.assertEqual(kinds(self.ceo), ["contract_review"])
        self.assertEqual(kinds(self.hr), ["contract_continue", "contract_draft", "contract_handover", "contract_redraft", "contract_send"])
        self.assertEqual(kinds(self.member), ["contract_confirm", "contract_send"])
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
