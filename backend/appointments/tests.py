from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from appointments import reminders
from appointments.models import Appointment
from leads.models import LeadStatusChange
from leads.tests import LeadCase
from lookups.models import RejectionReason
from notifications.models import Notification


class AppointmentCase(LeadCase):
    def when(self, hours=24):
        return (timezone.now() + timedelta(hours=hours)).isoformat()

    def make(self, user=None, **over):
        self.as_user(user or self.member)
        body = {"type": "meeting", "title": "Kick-off", "starts_at": self.when()}
        body.update(over)
        return self.client.post("/api/appointments/", body, format="json")

    def waiting(self, lead, days=3, user=None):
        self.as_user(user or self.head)
        return self.client.post(f"/api/leads/{lead.pk}/interactions/", {"type": "call", "outcome": "waiting", "next_follow_up": self.day(days)}, format="json")


class AppointmentApiTests(AppointmentCase):
    def test_access_by_role(self):
        self.assert_matrix("get", "/api/appointments/", {"ceo": 200, "marketing": 200, "commercial_head": 200, "commercial_member": 200, "*": 403})

    def test_all_five_types_and_optional_lead(self):
        lead = self.mk(assigned=self.member)
        for t in ("meeting", "call", "visit", "other"):
            self.assertEqual(self.make(type=t, title=t).status_code, 201, t)
        self.assertEqual(self.make(type="meeting", lead=lead.pk).data["lead_ref"], lead.ref)
        self.assertEqual(self.make(type="follow_up", lead=lead.pk).status_code, 201)
        self.assertEqual(self.make(type="follow_up").status_code, 400)  # a follow-up needs its lead
        self.assertEqual(self.make(type="party").status_code, 400)

    def test_validation(self):
        self.assertEqual(self.make(title=" ").status_code, 400)
        self.assertEqual(self.make(starts_at=(timezone.now() - timedelta(hours=1)).isoformat()).status_code, 400)
        self.assertEqual(self.make(ends_at=(timezone.now() + timedelta(hours=1)).isoformat()).status_code, 400)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_a_lead_you_cannot_see_is_refused(self):
        lead = self.mk(assigned=self.member2)
        self.assertEqual(self.make(user=self.member, lead=lead.pk).status_code, 400)

    def test_own_vs_manager_all(self):
        mine = self.make(user=self.member).data["id"]
        theirs = self.make(user=self.member2, title="Other").data["id"]
        self.as_user(self.member)
        ids = [r["id"] for r in self.client.get("/api/appointments/").data["results"]]
        self.assertEqual(ids, [mine])
        self.assertEqual(self.client.get(f"/api/appointments/{theirs}/").status_code, 404)
        for user in (self.head, self.users["ceo"]):
            self.as_user(user)
            self.assertEqual({r["id"] for r in self.client.get("/api/appointments/").data["results"]}, {mine, theirs})

    def test_only_the_commercial_head_assigns(self):
        res = self.make(user=self.member, owner=self.member2.pk)
        self.assertEqual(res.status_code, 403)
        res = self.make(user=self.head, owner=self.member2.pk)
        self.assertEqual((res.status_code, res.data["owner"]), (201, self.member2.pk))
        self.assertEqual(self.make(user=self.head, owner=self.users["hr_member"].pk).status_code, 400)  # not someone who can have appointments
        self.assertEqual(Notification.objects.filter(user=self.member2, kind="appointment_assigned").count(), 1)
        self.as_user(self.users["ceo"])
        self.assertEqual(self.client.post("/api/appointments/", {"title": "x", "owner": self.member.pk, "starts_at": self.when()}, format="json").status_code, 403)

    def test_assignees_endpoint_is_for_the_head(self):
        self.assert_matrix("get", "/api/appointments/assignees/", {"commercial_head": 200, "*": 403})

    def test_someone_else_cannot_change_mine(self):
        mine = self.make(user=self.member).data["id"]
        self.as_user(self.member2)
        self.assertEqual(self.client.post(f"/api/appointments/{mine}/cancel/", {}, format="json").status_code, 404)

    def test_complete_and_cancel_close_it_once(self):
        a = self.make().data["id"]
        self.assertEqual(self.client.post(f"/api/appointments/{a}/complete/", {}, format="json").data["status"], "done")
        self.assertEqual(self.client.post(f"/api/appointments/{a}/cancel/", {}, format="json").status_code, 400)
        b = self.make().data["id"]
        res = self.client.post(f"/api/appointments/{b}/cancel/", {"reason": "client away"}, format="json")
        self.assertEqual((res.data["status"], res.data["cancel_reason"]), ("cancelled", "client away"))

    def test_reschedule_notifies_the_owner_in_their_language(self):
        a = self.make(user=self.head, owner=self.member.pk).data["id"]
        self.member.preferred_language = "ar"
        self.member.save()
        self.as_user(self.head)
        res = self.client.post(f"/api/appointments/{a}/reschedule/", {"starts_at": self.when(48)}, format="json")
        self.assertEqual(res.status_code, 200)
        n = Notification.objects.get(user=self.member, kind="appointment_rescheduled")
        self.assertIn("جدولة", n.title)
        past = self.client.post(f"/api/appointments/{a}/reschedule/", {"starts_at": (timezone.now() - timedelta(hours=1)).isoformat()}, format="json")
        self.assertEqual(past.status_code, 400)


class FollowUpWorkflowTests(AppointmentCase):
    def test_waiting_creates_one_follow_up_on_the_date_and_a_history_line(self):
        lead = self.mk(assigned=self.member)
        self.assertEqual(self.waiting(lead, 3).status_code, 201)
        ap = lead.appointments.get()
        self.assertEqual((ap.type, ap.status, ap.owner), ("follow_up", "scheduled", self.member))
        self.assertEqual(timezone.localtime(ap.starts_at).date().isoformat(), self.day(3))
        h = list(lead.status_changes.values_list("from_status", "to_status"))
        self.assertEqual(h, [("new", "contacted"), ("contacted", "waiting")])
        self.assertEqual(str(lead.status_changes.last().follow_up_date), self.day(3))

    def test_waiting_again_replaces_the_follow_up(self):
        lead = self.mk(assigned=self.member)
        self.waiting(lead, 3)
        self.waiting(lead, 5)
        self.assertEqual(lead.appointments.filter(status="scheduled").count(), 1)
        self.assertEqual(lead.appointments.filter(status="cancelled").count(), 1)

    def test_waiting_date_must_be_in_the_future(self):
        lead = self.mk(assigned=self.member)
        self.assertEqual(self.waiting(lead, 0).status_code, 400)
        self.assertEqual(lead.appointments.count(), 0)
        self.assertEqual(lead.status_changes.count(), 0)  # nothing half-done

    def test_rejection_cancels_open_follow_ups_and_keeps_the_reason(self):
        lead = self.mk(assigned=self.member)
        self.waiting(lead, 3)
        self.as_user(self.head)
        res = self.client.post(f"/api/leads/{lead.pk}/interactions/", {"type": "call", "outcome": "rejected", "rejection_reason": RejectionReason.objects.first().pk}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(lead.appointments.filter(status="scheduled").count(), 0)
        self.assertEqual(lead.appointments.get().status, "cancelled")
        last = lead.status_changes.last()
        self.assertEqual((last.to_status, last.rejection_reason_id), ("rejected", RejectionReason.objects.first().pk))

    def test_acceptance_cancels_open_follow_ups(self):
        lead = self.mk(assigned=self.member)
        self.waiting(lead, 3)
        self.as_user(self.head)
        self.client.post(f"/api/leads/{lead.pk}/interactions/", {"type": "call", "outcome": "accepted"}, format="json")
        self.assertEqual(lead.appointments.filter(status="scheduled").count(), 0)

    def test_rescheduling_the_follow_up_moves_the_lead_date(self):
        lead = self.mk(assigned=self.member)
        self.waiting(lead, 3)
        ap = lead.appointments.get()
        self.as_user(self.member)
        new = timezone.now() + timedelta(days=9)
        self.assertEqual(self.client.post(f"/api/appointments/{ap.pk}/reschedule/", {"starts_at": new.isoformat()}, format="json").status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.next_follow_up, timezone.localtime(new).date())

    def test_a_waiting_leads_follow_up_cannot_be_cancelled_directly(self):
        lead = self.mk(assigned=self.member)
        self.waiting(lead, 3)
        self.as_user(self.member)
        self.assertEqual(self.client.post(f"/api/appointments/{lead.appointments.get().pk}/cancel/", {}, format="json").status_code, 400)

    def test_history_endpoint_lists_every_move_in_order(self):
        lead = self.mk(assigned=self.member)
        self.waiting(lead, 3)
        self.as_user(self.head)
        self.client.post(f"/api/leads/{lead.pk}/interactions/", {"type": "call", "outcome": "accepted"}, format="json")
        rows = self.client.get(f"/api/leads/{lead.pk}/history/").data
        self.assertEqual([(r["from_status"], r["to_status"]) for r in rows], [("new", "contacted"), ("contacted", "waiting"), ("waiting", "qualified")])
        self.assertTrue(all(r["changed_by_name"] for r in rows))
        self.as_user(self.member2)
        self.assertEqual(self.client.get(f"/api/leads/{lead.pk}/history/").status_code, 404)

    def test_a_failure_in_the_side_effect_rolls_the_status_back(self):
        from unittest import mock

        lead = self.mk(assigned=self.member)
        with mock.patch("appointments.services.sync_follow_up", side_effect=RuntimeError("boom")):
            self.as_user(self.head)
            self.client.raise_request_exception = False
            res = self.client.post(f"/api/leads/{lead.pk}/interactions/", {"type": "call", "outcome": "waiting", "next_follow_up": self.day(3)}, format="json")
        self.assertEqual(res.status_code, 500)
        lead.refresh_from_db()
        self.assertEqual((lead.status, lead.interactions.count(), lead.status_changes.count()), ("new", 0, 0))

    def test_new_lead_starts_its_history(self):
        self.as_role("marketing")
        res = self.client.post("/api/leads/", {"company_name": "Fresh", "phone": "0791234567"}, format="json")
        self.assertEqual(list(LeadStatusChange.objects.filter(lead_id=res.data["id"]).values_list("from_status", "to_status")), [("", "new")])


class ProcessNotificationsTests(AppointmentCase):
    def test_reminder_goes_out_once_even_when_run_twice(self):
        a = self.make(starts_at=self.when(0.5)).data["id"]
        out = StringIO()
        call_command("process_notifications", stdout=out)
        call_command("process_notifications", stdout=out)
        self.assertEqual(Notification.objects.filter(user=self.member, kind="appointment_reminder").count(), 1)
        self.assertIn("Notifications sent: 1", out.getvalue().splitlines()[0])
        self.assertIn("Notifications sent: 0", out.getvalue().splitlines()[1])
        self.assertTrue(Appointment.objects.filter(pk=a).exists())

    def test_far_and_closed_appointments_are_not_reminded(self):
        self.make(starts_at=self.when(30))
        b = self.make(starts_at=self.when(0.5)).data["id"]
        self.client.post(f"/api/appointments/{b}/cancel/", {}, format="json")
        self.assertEqual(reminders.run(), 0)

    def test_reminder_is_in_the_readers_language_and_again_after_a_reschedule(self):
        self.member.preferred_language = "ar"
        self.member.save()
        a = self.make(starts_at=self.when(0.5)).data["id"]
        reminders.run()
        self.assertIn("موعد", Notification.objects.get(user=self.member, kind="appointment_reminder").title)
        self.client.post(f"/api/appointments/{a}/reschedule/", {"starts_at": self.when(0.8)}, format="json")
        self.assertEqual(reminders.run(), 1)

    def test_lead_reminders_run_through_the_same_command_once(self):
        lead = self.mk(status="waiting", assigned=self.member, next_follow_up=self.today() - timedelta(days=2))
        call_command("process_notifications", stdout=StringIO())
        call_command("process_notifications", stdout=StringIO())
        self.assertEqual(Notification.objects.filter(user=self.member, kind="followup_overdue").count(), 1)
        self.assertTrue(lead.pk)

    def test_mark_one_and_mark_all_read_and_unread_count(self):
        for _ in range(3):
            self.make(user=self.head, owner=self.member.pk)
        self.as_user(self.member)
        count = lambda: self.client.get("/api/notifications/unread-count/").data["count"]  # noqa: E731
        self.assertEqual(count(), 3)
        first = self.client.get("/api/notifications/").data["results"][0]["id"]
        self.assertEqual(self.client.post(f"/api/notifications/{first}/read/").status_code, 204)
        self.assertEqual(count(), 2)
        self.client.post("/api/notifications/read-all/")
        self.assertEqual(count(), 0)
