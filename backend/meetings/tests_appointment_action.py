"""Fix 4: the appointments list says where a report can be written, and links to it once it exists."""
from django.db import connection
from django.test.utils import CaptureQueriesContext

from meetings.tests import MCase


class AppointmentReportActionTests(MCase):
    def flags(self, user, appt):
        self.as_user(user)
        res = self.client.get("/api/appointments/?page_size=50")
        self.assertEqual(res.status_code, 200)
        return next(r["permissions"] for r in res.data["results"] if r["id"] == appt.pk)

    def test_the_owner_can_write_a_report_for_a_completed_meeting_with_a_lead(self):
        a = self.appointment(self.lead())
        self.assertEqual(self.flags(self.member, a), {"can_edit": False, "can_reschedule": False, "can_complete": False, "can_cancel": False, "can_write_report": True, "report_id": None})

    def test_not_for_open_or_cancelled_meetings_or_ones_without_a_lead(self):
        for status in ("scheduled", "cancelled"):
            self.assertFalse(self.flags(self.member, self.appointment(self.lead(), status=status))["can_write_report"], status)
        a = self.appointment(self.lead())
        a.lead = None
        a.save(update_fields=["lead"])
        self.assertFalse(self.flags(self.member, a)["can_write_report"])

    def test_only_people_who_may_write_reports_and_work_the_meeting(self):
        a = self.appointment(self.lead())
        self.assertTrue(self.flags(self.head, a)["can_write_report"])  # the head sees every appointment
        self.assertTrue(self.flags(self.ceo, a)["can_write_report"] is False)  # the CEO reads and approves, never writes
        self.as_user(self.hr)  # HR has no appointments at all, so no action either
        self.assertEqual(self.client.get("/api/appointments/").status_code, 403)

    def test_once_written_the_action_becomes_a_link_for_those_who_can_open_it(self):
        a = self.appointment(self.lead())
        self.as_user(self.member)
        res = self.client.post("/api/meeting-reports/", {"appointment": a.pk, "summary": "Agreed the plan"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        f = self.flags(self.member, a)
        self.assertEqual((f["can_write_report"], f["report_id"]), (False, res.data["id"]))
        self.assertEqual(self.flags(self.head, a)["report_id"], res.data["id"])

    def test_a_report_id_is_only_shown_to_people_who_can_open_the_report(self):
        a = self.appointment(self.lead())
        self.as_user(self.member)
        report_id = self.client.post("/api/meeting-reports/", {"appointment": a.pk, "summary": "Agreed"}, format="json").data["id"]
        self.as_user(self.member2)
        self.assertEqual(self.client.get(f"/api/meeting-reports/{report_id}/").status_code, 404)
        self.assertNotIn(a.pk, [r["id"] for r in self.client.get("/api/appointments/").data["results"]])

    def test_the_list_does_not_ask_the_database_per_row(self):
        for _ in range(8):
            self.appointment(self.lead())
        self.as_user(self.member)
        with CaptureQueriesContext(connection) as few:
            self.client.get("/api/appointments/?page_size=50")
        for _ in range(8):
            self.appointment(self.lead())
        with CaptureQueriesContext(connection) as many:
            self.client.get("/api/appointments/?page_size=50")
        self.assertEqual(len(few), len(many))
