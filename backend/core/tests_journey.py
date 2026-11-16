"""The whole business, through the HTTP API, one role at a time, exactly in the order the company works.

Language does not change any rule (the API returns the same data to both); the browser journeys in docs/ verify the screens in English
and Arabic against the same flow. Three paths: the full one, a rejected lead, and a qualified lead that skips the quotation.
"""
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from accounts.models import ActionLog
from clients.models import Client
from contracts.models import Contract
from core.testing import PASSWORD, RoleCase, png_signature
from leads.models import Lead
from lookups.models import RejectionReason

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
CSV = "company_name,contact_name,phone,email,source,notes\nJourney Co,Rana,0795550001,r@journey.example,Fair,\nSecond Co,Omar,0795550002,,,\nThird Co,Lina,0795550003,,,\n"


class JourneyTests(RoleCase):
    def as_(self, role):
        self.as_role(role)
        return self.client

    def post(self, role, url, body=None, fmt="json", expect=None):
        res = self.as_(role).post(url, body or {}, format=fmt)
        if expect:
            self.assertEqual(res.status_code, expect, f"{role} POST {url} -> {res.status_code} {getattr(res, 'data', '')}")
        return res

    def upload(self, role, target, category, name="doc.pdf"):
        return self.post(role, f"/api/files/?target={target}", {"file": SimpleUploadedFile(name, PDF, content_type="application/pdf"), "category": category}, fmt="multipart", expect=201)

    def import_leads(self):
        res = self.post("marketing", "/api/leads/import/confirm/", {"file": SimpleUploadedFile("leads.csv", CSV.encode(), content_type="text/csv")}, fmt="multipart", expect=201)
        return list(Lead.objects.filter(batch_id=res.data["id"]).order_by("id"))

    def assign(self, lead):
        self.post("commercial_head", f"/api/leads/{lead.pk}/assign/", {"assigned_to": self.users["commercial_member"].pk}, expect=200)

    def qualify(self, lead):
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        # The first contact has to be logged before any outcome; the interaction itself can set the outcome.
        self.post("commercial_member", f"/api/leads/{lead.pk}/interactions/", {"type": "call", "notes": "Introduced the service", "outcome": "waiting", "next_follow_up": tomorrow}, expect=201)
        self.assertEqual(Lead.objects.get(pk=lead.pk).status, "waiting")
        self.post("commercial_member", f"/api/leads/{lead.pk}/outcome/", {"outcome": "accepted"}, expect=200)
        self.assertEqual(Lead.objects.get(pk=lead.pk).status, "qualified")

    def contract_to_handover(self, lead):
        c = self.post("commercial_member", "/api/contracts/", {"lead": lead.pk, "request_note": "Standard terms"}, expect=201).data
        cid = c["id"]
        self.post("hr_head", f"/api/contracts/{cid}/start/", expect=200)
        self.post("hr_head", f"/api/contracts/{cid}/draft/", {"body_en": "Agreement text", "payment_terms": "Monthly"}, expect=200)
        self.post("hr_head", f"/api/contracts/{cid}/send/", {"note": "Draft 1"}, expect=200)
        self.post("commercial_head", f"/api/contracts/{cid}/confirm/", expect=200)
        self.post("hr_head", f"/api/contracts/{cid}/send-to-client/", expect=200)
        self.post("commercial_member", f"/api/contracts/{cid}/client-copy/", {"file": SimpleUploadedFile("signed.pdf", PDF, content_type="application/pdf")}, fmt="multipart", expect=200)
        self.post("ceo", f"/api/contracts/{cid}/approve/", {"signature": png_signature()}, expect=200)
        done = self.post("hr_member", f"/api/contracts/{cid}/handover/", expect=200).data
        self.assertEqual(done["status"], "handed_over")
        return Contract.objects.get(pk=cid)

    def test_full_path_from_import_to_payroll_and_reports(self):
        leads = self.import_leads()
        self.assertEqual(len(leads), 3)
        lead = leads[0]
        self.assign(lead)
        self.qualify(lead)

        # Quotation: Commercial requests, HR prepares, the Commercial head signs, Commercial sends and records the outcome.
        q = self.post("commercial_member", "/api/quotations/", {"lead": lead.pk, "request_note": "Monthly plan"}, expect=201).data
        qid = q["id"]
        self.post("hr_member", f"/api/quotations/{qid}/start/", expect=200)
        draft = {"currency": "JOD", "valid_until": (timezone.localdate() + timedelta(days=30)).isoformat(), "lines": [{"description": "Bookkeeping", "quantity": "1", "unit_price": "400", "discount_percent": "0", "tax_percent": "0"}]}
        self.assertEqual(self.as_("hr_member").put(f"/api/quotations/{qid}/draft/", draft, format="json").status_code, 200)
        self.post("hr_member", f"/api/quotations/{qid}/submit/", expect=200)
        self.post("commercial_head", f"/api/quotations/{qid}/sign/", {"signature": png_signature()}, expect=200)
        self.post("commercial_member", f"/api/quotations/{qid}/send/", expect=200)
        self.post("commercial_member", f"/api/quotations/{qid}/outcome/", {"outcome": "confirmed"}, expect=200)

        # Contract and handover create the client in Onboarding.
        contract = self.contract_to_handover(lead)
        client = Client.objects.get(pk=contract.client_id)
        self.assertEqual(client.status, "onboarding")

        # Operation verifies the KYC checklist: the client becomes Active.
        for item in client.checklist.filter(required=True):
            self.upload("operation_member", f"checklist_item:{item.pk}", "kyc")
            self.post("operation_member", f"/api/operations/checklist/{item.pk}/verify/", expect=200)
        client.refresh_from_db()
        self.assertEqual(client.status, "active")

        # A recurring task appears today; it is completed with a note; a QA meeting is logged.
        self.post("operation_head", "/api/operations/recurring/", {"client": client.pk, "title": "Monthly reconciliation", "frequency": "monthly", "start_date": timezone.localdate().isoformat(), "assignee": self.users["operation_member"].pk}, expect=201)
        task = client.tasks.get()
        self.post("operation_member", f"/api/operations/tasks/{task.pk}/complete/", {"note": "All matched"}, expect=200)
        self.post("operation_head", "/api/operations/meetings/", {"client": client.pk, "held_on": timezone.localdate().isoformat(), "notes": "Reviewed the books"}, expect=201)

        # Payments: the head schedules and records; the CEO reads; the Commercial member cannot see any of it.
        due = (timezone.localdate() + timedelta(days=30)).isoformat()
        self.post("commercial_head", f"/api/payments/clients/{client.pk}/schedule/", {"currency": "JOD", "instalments": [{"due_date": due, "amount": "200.00"}, {"due_date": due, "amount": "200.00"}]}, expect=201)
        inst = client.instalments.order_by("number").first()
        self.post("commercial_head", f"/api/payments/instalments/{inst.pk}/payments/", {"amount": "200.00", "received_on": timezone.localdate().isoformat(), "method": "bank_transfer"}, expect=201)
        st = self.as_("ceo").get(f"/api/payments/clients/{client.pk}/")
        self.assertEqual(st.status_code, 200)
        self.assertEqual(self.as_("commercial_member").get(f"/api/payments/clients/{client.pk}/").status_code, 403)

        # HR: signing in is what attendance is made from; leave is requested and approved; payroll runs Draft -> Approved -> Paid.
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post("/api/auth/login/", {"email": self.users["hr_member"].email, "password": PASSWORD}, format="json").status_code, 200)
        self.assertTrue(ActionLog.objects.filter(user=self.users["hr_member"]).exists())
        today = self.as_("hr_member").get("/api/hr/attendance/mine/")
        self.assertEqual(today.status_code, 200)
        day = timezone.localdate() + timedelta(days=1)
        while day.weekday() in (4, 5) or day.year != timezone.localdate().year:
            day += timedelta(days=1) if day.year == timezone.localdate().year else -timedelta(days=60)
        ltype = self.as_("hr_member").get("/api/hr/leave-types/").data[0]["id"]
        req = self.post("hr_member", "/api/hr/leave/", {"leave_type": ltype, "start_date": day.isoformat(), "end_date": day.isoformat()}, expect=201).data
        self.post("hr_head", f"/api/hr/leave/{req['id']}/approve/", expect=200)
        for key, amount in (("hr_member", "800.00"), ("hr_head", "1500.00")):
            self.assertEqual(self.as_("hr_head").put(f"/api/hr/salaries/{self.users[key].pk}/", {"base_salary": amount, "currency": "JOD"}, format="json").status_code, 200)
        month = timezone.localdate().strftime("%Y-%m")
        run = self.post("hr_head", "/api/hr/payroll/runs/", {"month": month}, expect=201).data
        self.post("ceo", f"/api/hr/payroll/runs/{run['id']}/approve/", expect=200)
        self.post("hr_head", f"/api/hr/payroll/runs/{run['id']}/pay/", expect=200)
        slips = self.as_("hr_member").get("/api/hr/payslips/").data
        self.assertEqual([s["net"] for s in slips], ["800.00"])
        self.assertEqual(self.as_("operation_member").get("/api/hr/payslips/").data, [])

        # The CEO's reports see all of it; the forecast refuses (one quotation is far too little history) but says why.
        funnel = self.as_("ceo").get("/api/reports/funnel/").data
        created = next(s for s in funnel["series"] if s["key"] == "funnel")["points"][0]["value"]
        self.assertEqual(created, 3)
        fc = self.as_("ceo").get("/api/reports/forecast/").data
        self.assertTrue(fc["refused"])
        self.assertEqual(fc["method"]["min_sample"], 10)
        rev = self.as_("ceo").get("/api/reports/revenue/").data
        self.assertEqual(rev["kpis"]["JOD"]["overdue_instalments"], 0)
        self.assertEqual(self.as_("ceo").get("/api/search/?q=Journey").data["results"][0]["title"], "Journey Co")

    def test_rejected_path(self):
        lead = self.import_leads()[1]
        self.assign(lead)
        reason = RejectionReason.objects.filter(is_active=True).first()
        # An outcome before the first contact is refused; a rejection then needs a reason.
        self.assertEqual(self.post("commercial_member", f"/api/leads/{lead.pk}/outcome/", {"outcome": "rejected", "rejection_reason": reason.pk}).status_code, 400)
        self.assertEqual(self.post("commercial_member", f"/api/leads/{lead.pk}/interactions/", {"type": "call", "notes": "Called", "outcome": "rejected"}).status_code, 400)
        self.post("commercial_member", f"/api/leads/{lead.pk}/interactions/", {"type": "call", "notes": "Called", "outcome": "rejected", "rejection_reason": reason.pk}, expect=201)
        self.assertEqual(Lead.objects.get(pk=lead.pk).status, "rejected")
        # A rejected lead can neither be quoted nor contracted.
        self.assertEqual(self.post("commercial_member", "/api/quotations/", {"lead": lead.pk, "request_note": "x"}).status_code, 400)
        self.assertEqual(self.post("commercial_member", "/api/contracts/", {"lead": lead.pk, "request_note": "x"}).status_code, 400)
        funnel = self.as_("commercial_head").get("/api/reports/funnel/").data
        rejections = next(s for s in funnel["series"] if s["key"] == "lead_rejections")["points"]
        self.assertEqual(sum(p["value"] for p in rejections), 1)
        # Only the head can reopen it, and then it is contacted again.
        self.assertEqual(self.post("commercial_member", f"/api/leads/{lead.pk}/reopen/", {"note": "again"}).status_code, 403)
        self.post("commercial_head", f"/api/leads/{lead.pk}/reopen/", {"note": "Client called back"}, expect=200)
        self.assertNotEqual(Lead.objects.get(pk=lead.pk).status, "rejected")

    def test_skipped_quotation_path(self):
        lead = self.import_leads()[2]
        self.assign(lead)
        self.qualify(lead)
        # No contract before the quotation step is either confirmed or skipped.
        self.assertEqual(self.post("commercial_member", "/api/contracts/", {"lead": lead.pk, "request_note": "x"}).status_code, 400)
        self.post("commercial_member", f"/api/leads/{lead.pk}/skip-quotation/", expect=200)
        self.assertEqual(self.post("commercial_member", "/api/quotations/", {"lead": lead.pk, "request_note": "x"}).status_code, 400)
        contract = self.contract_to_handover(lead)
        self.assertEqual(Client.objects.get(pk=contract.client_id).status, "onboarding")
        self.assertFalse(lead.quotations.exists())
