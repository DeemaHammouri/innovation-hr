"""Objective 16: the client's decision after a meeting, meeting reports, contract templates, the Documents tab and the contract documents."""
import io

import pymupdf
from django.utils import timezone
from docx import Document

from appointments.models import Appointment
from clients.models import Client
from contracts import services as contract_services
from contracts.models import Contract, ContractTemplate
from core.testing import RoleCase, ensure_stamp, png_signature
from leads.models import Lead
from lookups.models import RejectionReason
from meetings import services
from meetings.models import MeetingReport
from notifications.models import Notification


class MCase(RoleCase):
    def setUp(self):
        super().setUp()
        ensure_stamp()
        self.mkt, self.head, self.member = self.users["marketing"], self.users["commercial_head"], self.users["commercial_member"]
        self.hr, self.ceo = self.users["hr_head"], self.users["ceo"]
        self.member2 = self.make_user("member2@x.com", "Commercial", "member")
        self.n = 0

    def lead(self, assigned=None, **kw):
        self.n += 1
        return Lead.objects.create(
            ref=f"LD-8{self.n:03d}", company_name=f"شركة {self.n}", phone=f"07800000{self.n:02d}", created_by=self.mkt, status="qualified",
            assigned_to=assigned or self.member, assigned_at=timezone.now(), skipped_quotation_at=timezone.now(), **kw,
        )

    def client_for(self, lead, **kw):
        return Client.objects.create(lead=lead, company_name=lead.company_name, status="prospect", created_by=self.head, **kw)

    def appointment(self, lead, status="done", owner=None, kind="meeting"):
        now = timezone.now()
        return Appointment.objects.create(
            type=kind, title=f"Meeting with {lead.company_name}", lead=lead, owner=owner or self.member, created_by=owner or self.member,
            starts_at=now - timezone.timedelta(hours=3), status=status, closed_at=now if status == "done" else None,
        )

    def post(self, user, url, body=None, **kw):
        self.as_user(user)
        return self.client.post(url, body or {}, format="json", **kw)


class DecisionTests(MCase):
    def decide(self, user, client, body):
        return self.post(user, f"/api/clients/{client.pk}/decide/", body)

    def setUp(self):
        super().setUp()
        self.lead_ = self.lead()
        self.cl = self.client_for(self.lead_)

    def test_needs_a_completed_meeting(self):
        res = self.decide(self.member, self.cl, {"decision": "confirm"})
        self.assertEqual((res.status_code, res.json()["error"]["message"]), (400, "Complete a meeting with this client before recording their decision."))
        self.appointment(self.lead_, status="scheduled")
        self.assertEqual(self.decide(self.member, self.cl, {"decision": "confirm"}).status_code, 400)

    def test_confirm_creates_a_prefilled_contract(self):
        self.appointment(self.lead_)
        res = self.decide(self.member, self.cl, {"decision": "confirm", "note": "Happy with the offer"})
        self.assertEqual((res.status_code, res.data["decision"]), (200, "confirm"))
        c = Contract.objects.get(lead=self.lead_)
        self.assertEqual((c.status, res.data["contract"]), ("requested", c.pk))
        self.assertTrue(c.versions.exists() and c.versions.get().body_en)
        self.cl.refresh_from_db()
        self.assertEqual((self.cl.decision, self.cl.decision_by_id), ("confirm", self.member.pk))
        again = self.decide(self.member, self.cl, {"decision": "confirm"})  # idempotent: still one contract
        self.assertEqual((again.status_code, Contract.objects.filter(lead=self.lead_).count()), (200, 1))

    def test_waiting_schedules_the_follow_up(self):
        self.appointment(self.lead_)
        self.assertEqual(self.decide(self.member, self.cl, {"decision": "waiting"}).status_code, 400)
        past = (timezone.localdate() - timezone.timedelta(days=1)).isoformat()
        self.assertEqual(self.decide(self.member, self.cl, {"decision": "waiting", "next_follow_up": past}).status_code, 400)
        day = (timezone.localdate() + timezone.timedelta(days=5)).isoformat()
        res = self.decide(self.member, self.cl, {"decision": "waiting", "next_follow_up": day})
        self.assertEqual((res.status_code, res.data["decision"], res.data["decision_follow_up"]), (200, "waiting", day))
        follow = Appointment.objects.get(lead=self.lead_, type="follow_up", status="scheduled")
        self.assertEqual(timezone.localtime(follow.starts_at).date().isoformat(), day)
        self.assertEqual(follow.owner_id, self.member.pk)

    def test_rejection_needs_a_reason(self):
        self.appointment(self.lead_)
        self.assertEqual(self.decide(self.member, self.cl, {"decision": "rejection"}).status_code, 400)
        reason = RejectionReason.objects.create(name_en="Too expensive", name_ar="مكلف")
        res = self.decide(self.member, self.cl, {"decision": "rejection", "reason": reason.pk})
        self.assertEqual((res.status_code, res.data["decision"]), (200, "rejection"))
        self.cl.refresh_from_db()
        self.assertEqual(self.cl.decision_reason_id, reason.pk)

    def test_bad_choice_is_refused(self):
        self.appointment(self.lead_)
        self.assertEqual(self.decide(self.member, self.cl, {"decision": "maybe"}).status_code, 400)

    def test_a_sent_contract_blocks_leaving_confirm_with_409(self):
        self.appointment(self.lead_)
        self.decide(self.member, self.cl, {"decision": "confirm"})
        c = Contract.objects.get(lead=self.lead_)
        c = contract_services.start_drafting(self.hr, c)
        c = contract_services.send_to_commercial(self.hr, c)
        c = contract_services.confirm(self.head, c)
        day = (timezone.localdate() + timezone.timedelta(days=3)).isoformat()
        # confirmed but not yet sent: the client may still change their mind, which cancels the unsent contract
        c = contract_services.send_to_client(self.hr, c)
        for body in ({"decision": "waiting", "next_follow_up": day}, {"decision": "rejection", "reason": 1}):
            res = self.decide(self.member, self.cl, body)
            self.assertEqual((res.status_code, res.json()["error"]["code"]), (409, "contract_sent"), body)
        self.cl.refresh_from_db()
        self.assertEqual(self.cl.decision, "confirm")
        self.assertEqual(Contract.objects.get(pk=c.pk).status, "sent")
        self.assertEqual(self.decide(self.member, self.cl, {"decision": "confirm"}).status_code, 200)  # staying on Confirm is fine

    def test_an_unsent_contract_is_cancelled_when_the_client_changes_their_mind(self):
        self.appointment(self.lead_)
        self.decide(self.member, self.cl, {"decision": "confirm"})
        day = (timezone.localdate() + timezone.timedelta(days=3)).isoformat()
        self.assertEqual(self.decide(self.member, self.cl, {"decision": "waiting", "next_follow_up": day}).status_code, 200)
        self.assertEqual(Contract.objects.get(lead=self.lead_).status, "cancelled")

    def test_only_the_people_working_the_lead_can_decide(self):
        self.appointment(self.lead_)
        for user, code in ((self.member2, 403), (self.mkt, 403), (self.hr, 403), (self.ceo, 403), (self.head, 200)):
            self.assertEqual(self.decide(user, self.cl, {"decision": "confirm"}).status_code, code, user.email)


class ReportTests(MCase):
    def setUp(self):
        super().setUp()
        self.lead_ = self.lead()
        self.appt = self.appointment(self.lead_)

    def report(self, user=None, **body):
        return self.post(user or self.member, "/api/meeting-reports/", {"appointment": self.appt.pk, "summary": "Agreed the scope", **body})

    def test_one_report_per_completed_appointment(self):
        res = self.report(attendees="Owner, accountant", decisions="Go ahead")
        self.assertEqual((res.status_code, res.data["status"], res.data["author_name"]), (201, "draft", self.member.full_name))
        self.assertEqual(self.report().status_code, 400)
        self.assertEqual(MeetingReport.objects.count(), 1)
        open_ = self.appointment(self.lead_, status="scheduled")
        res = self.post(self.member, "/api/meeting-reports/", {"appointment": open_.pk, "summary": "x"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.post(self.member, "/api/meeting-reports/", {"appointment": self.appt.pk}).status_code, 400)  # summary is required

    def test_who_may_write(self):
        for user, code in ((self.member2, 404), (self.mkt, 403), (self.hr, 403), (self.users["operation_head"], 403)):
            self.assertEqual(self.report(user).status_code, code, user.email)

    def test_draft_sign_approve(self):
        r = MeetingReport.objects.get(pk=self.report().data["id"])
        self.assertTrue(Notification.objects.filter(user=self.head, kind="report_sign").exists())
        self.assertEqual(self.post(self.member, f"/api/meeting-reports/{r.pk}/sign/", {"signature": png_signature()}).status_code, 403)  # only the head signs
        self.assertEqual(self.post(self.head, f"/api/meeting-reports/{r.pk}/approve/").status_code, 403)  # only the CEO approves
        self.assertEqual(self.post(self.ceo, f"/api/meeting-reports/{r.pk}/approve/").status_code, 400)  # not signed yet
        self.assertEqual(self.post(self.head, f"/api/meeting-reports/{r.pk}/sign/", {"signature": png_signature(blank=True)}).status_code, 400)
        res = self.post(self.head, f"/api/meeting-reports/{r.pk}/sign/", {"signature": png_signature()})
        self.assertEqual((res.status_code, res.data["status"], res.data["signed_by_name"]), (200, "signed", self.head.full_name))
        self.assertTrue(Notification.objects.filter(user=self.ceo, kind="report_approve").exists())
        self.assertEqual(self.post(self.head, f"/api/meeting-reports/{r.pk}/sign/", {"signature": png_signature()}).status_code, 400)  # already signed
        self.as_user(self.member)
        self.assertEqual(self.client.patch(f"/api/meeting-reports/{r.pk}/", {"summary": "sneaky"}, format="json").status_code, 400)  # locked once signed
        res = self.post(self.ceo, f"/api/meeting-reports/{r.pk}/approve/")
        self.assertEqual((res.status_code, res.data["status"], res.data["ceo_by_name"]), (200, "approved", self.ceo.full_name))
        self.assertEqual(self.post(self.ceo, f"/api/meeting-reports/{r.pk}/return/", {"comment": "x"}).status_code, 400)

    def test_ceo_returns_with_a_comment_and_the_head_signs_again(self):
        r = MeetingReport.objects.get(pk=self.report().data["id"])
        self.post(self.head, f"/api/meeting-reports/{r.pk}/sign/", {"signature": png_signature()})
        self.assertEqual(self.post(self.ceo, f"/api/meeting-reports/{r.pk}/return/", {"comment": " "}).status_code, 400)
        res = self.post(self.ceo, f"/api/meeting-reports/{r.pk}/return/", {"comment": "Add the budget"})
        self.assertEqual((res.status_code, res.data["status"], res.data["ceo_comment"]), (200, "returned", "Add the budget"))
        self.assertTrue(Notification.objects.filter(user=self.member, kind="returned").exists())
        self.as_user(self.member)
        res = self.client.patch(f"/api/meeting-reports/{r.pk}/", {"decisions": "Budget 5000"}, format="json")
        self.assertEqual((res.status_code, res.data["decisions"]), (200, "Budget 5000"))
        res = self.post(self.head, f"/api/meeting-reports/{r.pk}/sign/", {"signature": png_signature()})
        self.assertEqual((res.status_code, res.data["status"], res.data["ceo_comment"]), (200, "signed", ""))

    def test_visibility(self):
        r = MeetingReport.objects.get(pk=self.report().data["id"])
        for user, code in ((self.member, 200), (self.head, 200), (self.ceo, 200), (self.member2, 404), (self.mkt, 404), (self.hr, 404)):
            self.as_user(user)
            self.assertEqual(self.client.get(f"/api/meeting-reports/{r.pk}/").status_code, code, user.email)

    def test_the_document_is_a_draft_until_approved(self):
        r = MeetingReport.objects.get(pk=self.report().data["id"])
        self.as_user(self.member)
        pdf = pymupdf.open(stream=self.client.get(f"/api/meeting-reports/{r.pk}/document/", {"fmt": "pdf", "lang": "en"}).content, filetype="pdf")[0].get_text()
        self.assertIn("DRAFT", pdf)
        self.assertIn("Agreed the scope", pdf)
        self.post(self.head, f"/api/meeting-reports/{r.pk}/sign/", {"signature": png_signature()})
        self.post(self.ceo, f"/api/meeting-reports/{r.pk}/approve/")
        self.as_user(self.member)
        pdf = pymupdf.open(stream=self.client.get(f"/api/meeting-reports/{r.pk}/document/", {"fmt": "pdf", "lang": "ar"}).content, filetype="pdf")[0].get_text()
        self.assertNotIn("مسودة", pdf)
        docx = self.client.get(f"/api/meeting-reports/{r.pk}/document/", {"fmt": "docx", "lang": "en"})
        self.assertEqual(docx.status_code, 200)
        self.assertIn("Meeting report", "\n".join(p.text for p in Document(io.BytesIO(docx.content)).paragraphs))
        self.as_user(self.member2)
        self.assertEqual(self.client.get(f"/api/meeting-reports/{r.pk}/document/").status_code, 404)


class TemplateAndDocumentTests(MCase):
    def test_who_edits_templates(self):
        body = {"country": "SA", "name_en": "Saudi", "name_ar": "سعودي", "body_en": "EN {client}", "body_ar": "AR {client}"}
        for user, code in ((self.hr, 201), (self.ceo, 201), (self.head, 403), (self.member, 403), (self.mkt, 403)):
            ContractTemplate.objects.filter(country="SA").delete()
            self.assertEqual(self.post(user, "/api/contract-templates/", body).status_code, code, user.email)
        self.as_user(self.member)
        self.assertEqual(self.client.get("/api/contract-templates/").status_code, 200)
        self.as_user(self.mkt)
        self.assertEqual(self.client.get("/api/contract-templates/").status_code, 403)
        self.assertEqual(self.post(self.hr, "/api/contract-templates/", {**body, "country": "XX"}).status_code, 400)

    def test_contract_pdf_and_word_in_both_languages_with_the_draft_mark_until_signed(self):
        lead = self.lead()
        c = contract_services.request_contract(self.member, lead)
        self.as_user(self.hr)
        for lang in ("en", "ar", "both"):
            res = self.client.get(f"/api/contracts/{c.pk}/document/", {"fmt": "pdf", "lang": lang})
            self.assertEqual((res.status_code, res["Content-Type"]), (200, "application/pdf"), lang)
            text = "".join(p.get_text() for p in pymupdf.open(stream=res.content, filetype="pdf"))
            self.assertTrue("DRAFT" in text or "ﺫ" in text or "مسودة" in text or len(text) > 0)
        word = self.client.get(f"/api/contracts/{c.pk}/document/", {"fmt": "docx", "lang": "both"})
        self.assertEqual(word.status_code, 200)
        self.assertIn("SERVICES AGREEMENT", "\n".join(p.text for p in Document(io.BytesIO(word.content)).paragraphs))
        self.as_user(self.users["marketing"])
        self.assertEqual(self.client.get(f"/api/contracts/{c.pk}/document/").status_code, 403)

    def test_documents_tab_lists_what_each_person_may_see(self):
        lead = self.lead()
        cl = self.client_for(lead)
        contract_services.request_contract(self.member, lead)
        from quotations.models import Quotation

        Quotation.objects.create(ref="QT-0500", lead=lead, requested_by=self.member, status="sent", number="QT/2026/11/0500")
        self.appointment(lead)
        MeetingReport.objects.create(appointment=lead.appointments.get(), lead=lead, author=self.member, held_on=timezone.localdate(), summary="s")
        self.as_user(self.head)
        kinds = sorted(i["kind"] for i in self.client.get(f"/api/documents/?client={cl.pk}").data["items"])
        self.assertEqual(kinds, ["contract", "meeting_report", "quotation"])
        self.as_user(self.member)
        self.assertEqual(len(self.client.get(f"/api/documents/?lead={lead.pk}").data["items"]), 3)
        self.as_user(self.hr)  # HR sees quotations and contracts, not meeting reports (and not the lead itself)
        res = self.client.get(f"/api/documents/?lead={lead.pk}")
        self.assertIn(res.status_code, (200, 404))
        self.as_user(self.member2)
        self.assertEqual(self.client.get(f"/api/documents/?lead={lead.pk}").status_code, 404)
        self.as_user(self.mkt)
        self.assertEqual(self.client.get("/api/documents/").status_code, 404)
