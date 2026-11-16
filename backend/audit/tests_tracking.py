"""Objective 17: urgent alerts and the administration's process-tracking page. The clock is moved by patching `timezone.now`, so every
threshold is reproduced without waiting."""
from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from appointments.models import Appointment
from audit.models import record
from core.testing import RoleCase
from leads.models import Lead
from notifications import urgent
from notifications.models import Notification
from quotations import services as qs
from quotations.models import Quotation


def at(moment):
    """Make the notification code see `moment` as now."""
    return mock.patch("notifications.urgent.timezone.now", return_value=moment)


class UrgentCase(RoleCase):
    def setUp(self):
        super().setUp()
        self.member, self.head, self.mkt = self.users["commercial_member"], self.users["commercial_head"], self.users["marketing"]
        self.hr, self.hr2, self.ceo = self.users["hr_head"], self.users["hr_member"], self.users["ceo"]
        self.n = 0

    def lead(self, **kw):
        self.n += 1
        fields = dict(
            ref=f"LD-9{self.n:03d}", company_name=f"Client {self.n}", phone=f"07900000{self.n:02d}", created_by=self.mkt, status="qualified",
            assigned_to=self.member, assigned_at=timezone.now(),
        )
        return Lead.objects.create(**{**fields, **kw})

    def kinds(self, user, kind):
        return Notification.objects.filter(user=user, kind=kind).count()


class HrAlertTests(UrgentCase):
    def assigned_quotation(self):
        q = qs.request_quotation(self.member, self.lead())
        qs.assign(self.hr, q, self.hr2.pk)
        return Quotation.objects.get(pk=q.pk)

    def test_alert_after_60_minutes_without_submitting_and_only_once(self):
        q = self.assigned_quotation()
        start = timezone.now()
        with at(start + timedelta(minutes=59)):
            self.assertEqual(urgent.run(), 0)
        with at(start + timedelta(minutes=61)):
            self.assertEqual(urgent.run(), 1)
            self.assertEqual(urgent.run(), 0)  # a second run sends nothing
        with at(start + timedelta(hours=9)):
            self.assertEqual(urgent.run(), 0)  # never repeated for the same case
        n = Notification.objects.get(user=self.hr2, kind="urgent_hr")
        self.assertEqual((n.link, q.ref in n.title), (f"/quotations/{q.pk}", True))

    def test_no_alert_once_it_is_submitted_and_a_new_assignment_is_a_new_case(self):
        q = self.assigned_quotation()
        start = timezone.now()
        with at(start + timedelta(minutes=70)):
            urgent.run()
        self.assertEqual(self.kinds(self.hr2, "urgent_hr"), 1)
        Quotation.objects.filter(pk=q.pk).update(status="in_review")
        with at(start + timedelta(hours=5)):
            self.assertEqual(urgent.run() - self.commercial_count(), 0)
        # handed back and assigned again: a fresh case, alerted again after its own 60 minutes
        Quotation.objects.filter(pk=q.pk).update(status="changes_requested")
        again = timezone.now() + timedelta(hours=6)
        with mock.patch("audit.models.timezone.now", return_value=again):
            qs.assign(self.hr, Quotation.objects.get(pk=q.pk), self.hr2.pk)
        with at(again + timedelta(minutes=61)):
            self.assertGreaterEqual(urgent.run(), 1)
        self.assertEqual(self.kinds(self.hr2, "urgent_hr"), 2)

    def commercial_count(self):
        return urgent.commercial_alerts(timezone.now() + timedelta(hours=5))

    def test_unassigned_quotations_do_not_alert(self):
        qs.request_quotation(self.member, self.lead())
        with at(timezone.now() + timedelta(hours=3)):
            self.assertEqual(urgent.run(), 0)

    @override_settings(URGENT_HR_MINUTES=10)
    def test_the_threshold_comes_from_settings(self):
        self.assigned_quotation()
        start = timezone.now()
        with at(start + timedelta(minutes=9)):
            self.assertEqual(urgent.run(), 0)
        with at(start + timedelta(minutes=11)):
            self.assertEqual(urgent.run(), 1)


class CommercialAlertTests(UrgentCase):
    def submitted(self):
        from quotations.models import QuotationLine, QuotationVersion

        q = Quotation.objects.create(ref="QT-0900", lead=self.lead(), requested_by=self.member, status="in_review", prepared_by=self.hr2)
        QuotationVersion.objects.create(quotation=q, number=1, created_by=self.hr2, submitted_at=timezone.now())
        return q

    def test_alert_the_commercial_head_60_minutes_after_submission(self):
        q = self.submitted()
        start = timezone.now()
        with at(start + timedelta(minutes=59)):
            self.assertEqual(urgent.run(), 0)
        with at(start + timedelta(minutes=61)):
            self.assertEqual(urgent.run(), 1)
            self.assertEqual(urgent.run(), 0)
        self.assertEqual(self.kinds(self.head, "urgent_commercial"), 1)
        self.assertEqual(self.kinds(self.member, "urgent_commercial"), 0)
        self.assertEqual(Notification.objects.get(kind="urgent_commercial").link, f"/quotations/{q.pk}")

    def test_signed_quotations_do_not_alert(self):
        q = self.submitted()
        Quotation.objects.filter(pk=q.pk).update(status="signed")
        with at(timezone.now() + timedelta(hours=5)):
            self.assertEqual(urgent.run(), 0)

    @override_settings(URGENT_COMMERCIAL_MINUTES=5)
    def test_threshold_from_settings(self):
        self.submitted()
        with at(timezone.now() + timedelta(minutes=6)):
            self.assertEqual(urgent.run(), 1)


class AppointmentAlertTests(UrgentCase):
    def appointment(self, status="scheduled"):
        return Appointment.objects.create(type="meeting", title="Visit", owner=self.member, created_by=self.member, starts_at=timezone.now() + timedelta(minutes=30), status=status)

    def test_alert_the_owner_60_minutes_after_the_time_while_still_open(self):
        a = self.appointment()
        with at(a.starts_at + timedelta(minutes=59)):
            self.assertEqual(urgent.run(), 0)
        with at(a.starts_at + timedelta(minutes=61)):
            self.assertEqual(urgent.run(), 1)
            self.assertEqual(urgent.run(), 0)
        self.assertEqual(self.kinds(self.member, "urgent_appointment"), 1)

    def test_closed_appointments_do_not_alert_and_a_rescheduled_one_alerts_again(self):
        done = self.appointment("done")
        a = self.appointment()
        with at(a.starts_at + timedelta(minutes=90)):
            self.assertEqual(urgent.run(), 1)
        Appointment.objects.filter(pk=a.pk).update(starts_at=a.starts_at + timedelta(days=1))
        with at(a.starts_at + timedelta(days=1, minutes=61)):
            self.assertEqual(urgent.run(), 1)
        self.assertEqual(self.kinds(self.member, "urgent_appointment"), 2)
        self.assertEqual(done.status, "done")

    def test_the_scheduled_command_runs_the_alerts(self):
        a = self.appointment()
        with at(a.starts_at + timedelta(minutes=61)):
            call_command("process_notifications")
        self.assertEqual(self.kinds(self.member, "urgent_appointment"), 1)


class TrackingPageTests(UrgentCase):
    def test_only_the_administration_can_open_it(self):
        for key in ("ceo",):
            self.as_role(key)
            self.assertEqual(self.client.get("/api/admin/tracking/").status_code, 200)
            self.assertEqual(self.client.get("/api/admin/activity/").status_code, 200)
        for key in ("marketing", "commercial_head", "commercial_member", "hr_head", "hr_member", "operation_head", "operation_member"):
            self.as_role(key)
            self.assertEqual(self.client.get("/api/admin/tracking/").status_code, 403, key)
            self.assertEqual(self.client.get("/api/admin/activity/").status_code, 403, key)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/admin/tracking/").status_code, 401)

    def test_it_shows_todays_changes_and_what_is_late(self):
        lead = self.lead(next_follow_up=timezone.localdate() - timedelta(days=3), status="waiting")
        record(self.member, lead, "status_changed", from_value="new", to_value="waiting")
        a = Appointment.objects.create(type="meeting", title="Missed visit", owner=self.member, created_by=self.member, starts_at=timezone.now() - timedelta(hours=3))
        q = qs.request_quotation(self.member, self.lead())
        qs.assign(self.hr, q, self.hr2.pk)
        self.as_role("ceo")
        d = self.client.get("/api/admin/tracking/").data
        self.assertIn("status_changed", [e["action"] for e in d["changed_today"]])
        self.assertEqual([m["id"] for m in d["missed_appointments"]], [a.pk])
        self.assertEqual([o["id"] for o in d["overdue_follow_ups"]], [lead.pk])
        self.assertEqual(d["thresholds"], {"hr": 60, "commercial": 60, "appointment": 60})
        self.assertIn("waiting", d["pipeline"]["leads"])
        self.assertTrue(any(t["name"] == self.member.full_name and t["today"] >= 1 for t in d["team"]))

    def test_late_quotations_appear_when_the_clock_passes_the_threshold(self):
        q = qs.request_quotation(self.member, self.lead())
        qs.assign(self.hr, q, self.hr2.pk)
        self.as_role("ceo")
        self.assertEqual(self.client.get("/api/admin/tracking/").data["late_quotations"], [])
        with mock.patch("audit.tracking.timezone.now", return_value=timezone.now() + timedelta(minutes=75)):
            late = self.client.get("/api/admin/tracking/").data["late_quotations"]
        self.assertEqual([(x["id"], x["stage"], x["person"]) for x in late], [(q.pk, "preparation", self.hr2.full_name)])
        self.assertGreaterEqual(late[0]["minutes_late"], 14)

    def test_the_feed_filters_by_employee_and_action(self):
        lead = self.lead()
        record(self.member, lead, "contacted")
        record(self.head, lead, "assigned")
        record(self.head, lead, "contacted")
        self.as_role("ceo")
        get = lambda q: self.client.get(f"/api/admin/activity/{q}").data
        self.assertEqual(get("")["count"], 3)
        self.assertEqual({e["actor"] for e in get(f"?actor={self.head.pk}")["results"]}, {self.head.pk})
        self.assertEqual(get("?action=contacted")["count"], 2)
        self.assertEqual(get(f"?actor={self.head.pk}&action=contacted")["count"], 1)
        self.assertEqual(get("?kind=lead")["count"], 3)
        self.assertEqual(get("?kind=quotation")["count"], 0)
        self.assertEqual(get(f"?from={timezone.localdate()}&to={timezone.localdate()}")["count"], 3)
        self.assertEqual(get(f"?to={timezone.localdate() - timedelta(days=1)}")["count"], 0)
        f = self.client.get("/api/admin/activity/filters/").data
        self.assertEqual(set(f["actions"]), {"assigned", "contacted"})
        self.assertEqual({p["id"] for p in f["people"]}, {self.member.pk, self.head.pk})
