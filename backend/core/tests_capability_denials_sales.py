"""Denial tests for the rule-level capabilities of the sales area (leads, appointments, quotations, contracts, meeting reports).

Each capability gets an allowed case and a denied case. Both use a role built from an exact capability set: the minimum for the area
(for example `lead.access`) plus the capability under test, and the same role with only that one capability removed. The records are made
through the same fixtures the feature tests use, and every denied case asserts a real refusal (403 or 404) or an absent record.
"""
from appointments.tests import AppointmentCase
from contracts.tests import CCase
from core.tests_capabilities import custom_role, custom_user
from leads.models import ImportBatch, Lead
from leads.tests import LeadCase
from meetings.models import MeetingReport
from meetings.tests import MCase
from quotations.tests import QCase


def user_with(key, *codes):
    return custom_user(custom_role(key, list(codes)))


def ids(res):
    return {r["id"] for r in res.data["results"]}


class LeadCapabilityDenials(LeadCase):
    def sees(self, user, lead):
        """(is the lead in the list, status of the detail call)."""
        self.as_user(user)
        listed = lead.pk in ids(self.client.get("/api/leads/"))
        return listed, self.client.get(f"/api/leads/{lead.pk}/").status_code

    def test_lead_view_all_allowed(self):
        lead = self.mk()  # created by Marketing, assigned to nobody
        user = user_with("v_all_yes", "lead.access", "lead.view_all")
        self.assertEqual(self.sees(user, lead), (True, 200))

    def test_lead_view_all_denied_without_it(self):
        lead = self.mk()
        user = user_with("v_all_no", "lead.access")
        self.assertEqual(self.sees(user, lead), (False, 404))

    def test_lead_view_assigned_allowed(self):
        user = user_with("v_asg_yes", "lead.access", "lead.view_assigned")
        lead = self.mk(assigned=user)
        self.assertEqual(self.sees(user, lead), (True, 200))

    def test_lead_view_assigned_denied_without_it(self):
        user = user_with("v_asg_no", "lead.access")
        lead = self.mk(assigned=user)
        self.assertEqual(self.sees(user, lead), (False, 404))

    def test_lead_view_assigned_never_shows_someone_elses_lead(self):
        user = user_with("v_asg_other", "lead.access", "lead.view_assigned")
        lead = self.mk(assigned=self.member)
        self.assertEqual(self.sees(user, lead), (False, 404))

    def test_lead_view_created_allowed(self):
        user = user_with("v_cr_yes", "lead.access", "lead.view_created")
        lead = self.mk(created_by=user)
        self.assertEqual(self.sees(user, lead), (True, 200))

    def test_lead_view_created_denied_without_it(self):
        user = user_with("v_cr_no", "lead.access")
        lead = self.mk(created_by=user)
        self.assertEqual(self.sees(user, lead), (False, 404))

    def test_lead_work_assigned_allowed(self):
        user = user_with("w_asg_yes", "lead.access", "lead.view_assigned", "lead.work_assigned")
        lead = self.mk(assigned=user)
        self.as_user(user)
        res = self.client.post(f"/api/leads/{lead.pk}/interactions/", {"type": "call", "notes": "Spoke to them"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(lead.interactions.count(), 1)

    def test_lead_work_assigned_denied_without_it(self):
        user = user_with("w_asg_no", "lead.access", "lead.view_assigned")  # sees the lead, may not work it
        lead = self.mk(assigned=user)
        self.as_user(user)
        self.assertEqual(self.client.get(f"/api/leads/{lead.pk}/").status_code, 200)
        res = self.client.post(f"/api/leads/{lead.pk}/interactions/", {"type": "call", "notes": "Spoke to them"}, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(self.client.post(f"/api/leads/{lead.pk}/outcome/", {"outcome": "accepted"}, format="json").status_code, 403)
        self.assertEqual(lead.interactions.count(), 0)

    def test_lead_batches_all_allowed(self):
        batch = ImportBatch.objects.create(ref="IB-0501", filename="theirs.csv", created_by=self.head)
        user = user_with("b_all_yes", "lead.access", "lead.batches", "lead.batches_all")
        self.as_user(user)
        self.assertIn(batch.pk, ids(self.client.get("/api/import-batches/")))
        self.assertEqual(self.client.get(f"/api/import-batches/{batch.pk}/").status_code, 200)

    def test_lead_batches_all_denied_without_it(self):
        theirs = ImportBatch.objects.create(ref="IB-0502", filename="theirs.csv", created_by=self.head)
        user = user_with("b_all_no", "lead.access", "lead.batches")
        mine = ImportBatch.objects.create(ref="IB-0503", filename="mine.csv", created_by=user)
        self.as_user(user)
        self.assertEqual(ids(self.client.get("/api/import-batches/")), {mine.pk})
        self.assertEqual(self.client.get(f"/api/import-batches/{theirs.pk}/").status_code, 404)

    def test_lead_edit_created_allowed(self):
        user = user_with("e_cr_yes", "lead.access", "lead.view_created", "lead.edit_created")
        lead = self.mk(created_by=user)
        self.as_user(user)
        self.assertEqual(self.client.patch(f"/api/leads/{lead.pk}/", {"contact_name": "New Person"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"/api/leads/{lead.pk}/archive/", {"reason": "Added by mistake"}, format="json").status_code, 200)
        self.assertTrue(Lead.objects.get(pk=lead.pk).archived_at)

    def test_lead_edit_created_denied_without_it(self):
        user = user_with("e_cr_no", "lead.access", "lead.view_created")
        lead = self.mk(created_by=user)
        self.as_user(user)
        self.assertEqual(self.client.get(f"/api/leads/{lead.pk}/").status_code, 200)
        self.assertEqual(self.client.patch(f"/api/leads/{lead.pk}/", {"contact_name": "New Person"}, format="json").status_code, 403)
        self.assertEqual(self.client.post(f"/api/leads/{lead.pk}/archive/", {"reason": "Added by mistake"}, format="json").status_code, 403)
        lead.refresh_from_db()
        self.assertIsNone(lead.archived_at)
        self.assertEqual(lead.contact_name, "")


class AppointmentCapabilityDenials(AppointmentCase):
    def test_appointment_view_all_allowed(self):
        appt = self.make(user=self.member).data["id"]
        user = user_with("a_all_yes", "appointment.access", "appointment.view_all")
        self.as_user(user)
        self.assertIn(appt, ids(self.client.get("/api/appointments/")))
        self.assertEqual(self.client.get(f"/api/appointments/{appt}/").status_code, 200)

    def test_appointment_view_all_denied_without_it(self):
        appt = self.make(user=self.member).data["id"]
        user = user_with("a_all_no", "appointment.access")
        self.as_user(user)
        self.assertNotIn(appt, ids(self.client.get("/api/appointments/")))
        self.assertEqual(self.client.get(f"/api/appointments/{appt}/").status_code, 404)


class QuotationCapabilityDenials(QCase):
    def test_quotation_view_all_allowed(self):
        q = self.quote()
        user = user_with("q_all_yes", "quotation.access", "quotation.view_all")
        self.as_user(user)
        self.assertIn(q.pk, ids(self.client.get("/api/quotations/")))
        self.assertEqual(self.client.get(f"/api/quotations/{q.pk}/").status_code, 200)

    def test_quotation_view_all_denied_without_it(self):
        q = self.quote()
        user = user_with("q_all_no", "quotation.access")
        self.as_user(user)
        self.assertNotIn(q.pk, ids(self.client.get("/api/quotations/")))
        self.assertEqual(self.client.get(f"/api/quotations/{q.pk}/").status_code, 404)

    def test_quotation_view_assigned_allowed(self):
        user = user_with("q_asg_yes", "quotation.access", "quotation.view_assigned")
        q = self.quote(lead=self.lead(assigned=user))
        other = self.quote()  # on a lead assigned to someone else
        self.as_user(user)
        self.assertEqual(ids(self.client.get("/api/quotations/")), {q.pk})
        self.assertEqual(self.client.get(f"/api/quotations/{q.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/quotations/{other.pk}/").status_code, 404)

    def test_quotation_view_assigned_denied_without_it(self):
        user = user_with("q_asg_no", "quotation.access")
        q = self.quote(lead=self.lead(assigned=user))
        self.as_user(user)
        self.assertNotIn(q.pk, ids(self.client.get("/api/quotations/")))
        self.assertEqual(self.client.get(f"/api/quotations/{q.pk}/").status_code, 404)


class ContractCapabilityDenials(CCase):
    def test_contract_view_all_allowed(self):
        c = self.contract()
        user = user_with("c_all_yes", "contract.access", "contract.view_all")
        self.as_user(user)
        self.assertIn(c.pk, ids(self.client.get("/api/contracts/")))
        self.assertEqual(self.client.get(f"/api/contracts/{c.pk}/").status_code, 200)

    def test_contract_view_all_denied_without_it(self):
        c = self.contract()
        user = user_with("c_all_no", "contract.access")
        self.as_user(user)
        self.assertNotIn(c.pk, ids(self.client.get("/api/contracts/")))
        self.assertEqual(self.client.get(f"/api/contracts/{c.pk}/").status_code, 404)

    def test_contract_view_assigned_allowed(self):
        user = user_with("c_asg_yes", "contract.access", "contract.view_assigned")
        c = self.contract(lead=self.lead(assigned=user))
        other = self.contract()
        self.as_user(user)
        self.assertEqual(ids(self.client.get("/api/contracts/")), {c.pk})
        self.assertEqual(self.client.get(f"/api/contracts/{c.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/contracts/{other.pk}/").status_code, 404)

    def test_contract_view_assigned_denied_without_it(self):
        user = user_with("c_asg_no", "contract.access")
        c = self.contract(lead=self.lead(assigned=user))
        self.as_user(user)
        self.assertNotIn(c.pk, ids(self.client.get("/api/contracts/")))
        self.assertEqual(self.client.get(f"/api/contracts/{c.pk}/").status_code, 404)


class MeetingReportCapabilityDenials(MCase):
    def make_report(self):
        appt = self.appointment(self.lead())
        res = self.post(self.member, "/api/meeting-reports/", {"appointment": appt.pk, "summary": "Agreed the scope"})
        self.assertEqual(res.status_code, 201)
        return MeetingReport.objects.get(pk=res.data["id"])

    def test_meeting_report_view_all_allowed(self):
        r = self.make_report()
        user = user_with("m_all_yes", "meeting_report.write", "meeting_report.view_all")
        self.as_user(user)
        self.assertIn(r.pk, ids(self.client.get("/api/meeting-reports/")))
        self.assertEqual(self.client.get(f"/api/meeting-reports/{r.pk}/").status_code, 200)
        # the same capability lets them write the report of someone else's meeting
        second = self.appointment(self.lead())
        res = self.client.post("/api/meeting-reports/", {"appointment": second.pk, "summary": "Covered for a colleague"}, format="json")
        self.assertEqual(res.status_code, 201)

    def test_meeting_report_view_all_denied_without_it(self):
        r = self.make_report()
        user = user_with("m_all_no", "meeting_report.write")
        self.as_user(user)
        self.assertNotIn(r.pk, ids(self.client.get("/api/meeting-reports/")))
        self.assertEqual(self.client.get(f"/api/meeting-reports/{r.pk}/").status_code, 404)
        second = self.appointment(self.lead())
        res = self.client.post("/api/meeting-reports/", {"appointment": second.pk, "summary": "Not mine to write"}, format="json")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(MeetingReport.objects.count(), 1)
