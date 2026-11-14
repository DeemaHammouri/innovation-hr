import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import ActionLog
from audit.models import AuditEntry
from core.roles import ALL_ROLES
from core.testing import RoleCase
from hr import attendance, leave, payroll
from hr.models import EmployeeSalary, LeaveRequest, LeaveType, PayrollEntry, PayrollRun
from lookups.models import WorkHours
from notifications.models import Notification

TODAY = lambda: timezone.localdate()
D = lambda n: (TODAY() + timedelta(days=n)).isoformat()


def at(day, hh, mm=0, ss=0):
    return timezone.make_aware(datetime(day.year, day.month, day.day, hh, mm, ss))


def next_working_day(start, offset=0):
    d, n = start, -1
    while True:
        if d.weekday() not in leave.weekend():
            n += 1
            if n >= offset:
                return d
        d += timedelta(days=1)


class HCase(RoleCase):
    def setUp(self):
        super().setUp()
        self.ceo, self.hrh, self.hrm = self.users["ceo"], self.users["hr_head"], self.users["hr_member"]
        self.mem = self.users["commercial_member"]
        WorkHours.objects.update_or_create(pk=1, defaults={"work_start": "09:00", "work_end": "17:00", "grace_minutes": 15})
        self.annual = LeaveType.objects.get(name_en="Annual leave")
        self.unpaid = LeaveType.objects.get(name_en="Unpaid leave")

    def log(self, user, action, when):
        return ActionLog.objects.create(user=user, action=action, timestamp=when)


# ===================== attendance =====================
class AttendanceTests(HCase):
    day = date(2026, 11, 3)

    def rows(self, user, day=None):
        d = day or self.day
        return attendance.rows_for([user], d, d)

    def test_first_in_last_out_and_hours(self):
        self.log(self.mem, "login", at(self.day, 8, 50))
        self.log(self.mem, "login", at(self.day, 12, 0))  # a second sign-in does not move the first
        self.log(self.mem, "logout", at(self.day, 13, 0))
        self.log(self.mem, "logout", at(self.day, 17, 20))
        (r,) = self.rows(self.mem)
        self.assertEqual((r["first_in"].strftime("%H:%M"), r["last_out"].strftime("%H:%M"), r["hours"], r["late"], r["open"]), ("08:50", "17:20", 8.5, False, False))

    def test_late_flag_uses_work_start_plus_grace(self):
        for i, (mm, ss, late) in enumerate([(15, 0, False), (15, 59, False), (16, 0, True), (0, 0, False)]):
            u = self.make_user(f"late{i}@x.com", "Operation")
            self.log(u, "login", at(self.day, 9, mm, ss))
            (r,) = self.rows(u)
            self.assertEqual(r["late"], late, (mm, ss))
        u = self.make_user("l9@x.com", "Operation")
        self.log(u, "login", at(self.day, 9, 40))
        self.assertEqual(self.rows(u)[0]["minutes_late"], 40)

    def test_follows_the_ceo_configured_hours(self):
        WorkHours.objects.update(work_start="08:00", grace_minutes=0)
        self.log(self.mem, "login", at(self.day, 8, 5))
        self.assertTrue(self.rows(self.mem)[0]["late"])
        WorkHours.objects.update(work_start="10:00", grace_minutes=30)
        self.assertFalse(self.rows(self.mem)[0]["late"])

    def test_open_day_has_no_hours(self):
        self.log(self.mem, "login", at(self.day, 9, 0))
        (r,) = self.rows(self.mem)
        self.assertEqual((r["hours"], r["open"], r["last_out"]), (None, True, None))

    def test_logout_without_login_that_day_is_ignored(self):
        self.log(self.mem, "login", at(self.day, 22, 0))
        self.log(self.mem, "logout", at(self.day + timedelta(days=1), 1, 0))
        self.assertEqual(len(attendance.rows_for([self.mem], self.day, self.day + timedelta(days=1))), 1)
        self.assertTrue(self.rows(self.mem)[0]["open"])

    def test_logout_before_first_login_does_not_count(self):
        self.log(self.mem, "logout", at(self.day, 7, 0))
        self.log(self.mem, "login", at(self.day, 9, 0))
        self.assertTrue(self.rows(self.mem)[0]["open"])

    def test_days_are_local_days(self):
        self.log(self.mem, "login", at(self.day, 0, 30))  # just after local midnight (still the previous day in UTC)
        self.log(self.mem, "logout", at(self.day, 23, 30))
        (r,) = self.rows(self.mem)
        self.assertEqual((r["date"], r["hours"]), (self.day, 23.0))
        self.assertEqual(self.rows(self.mem, self.day - timedelta(days=1)), [])

    def test_other_people_are_not_mixed_in(self):
        self.log(self.mem, "login", at(self.day, 9, 0))
        self.log(self.hrm, "login", at(self.day, 9, 0))
        self.assertEqual({r["user"] for r in attendance.rows_for([self.mem], self.day, self.day)}, {self.mem.pk})

    def test_mine_endpoint_is_own_only_for_every_role(self):
        for key in ALL_ROLES:
            self.log(self.users[key], "login", at(self.day, 9, 5))
        for key in ALL_ROLES:
            self.as_role(key)
            res = self.client.get("/api/hr/attendance/mine/?month=2026-11")
            self.assertEqual(res.status_code, 200, key)
            self.assertEqual({r["user"] for r in res.data["rows"]}, {self.users[key].pk}, key)
            self.assertEqual(res.data["summary"]["days"], 1)
            self.assertEqual(res.data["work_hours"], {"work_start": "09:00", "work_end": "17:00", "grace_minutes": 15})

    def test_mine_validation_and_summary(self):
        for n, (h, mm) in enumerate([(9, 0), (9, 30)]):
            d = self.day + timedelta(days=n)
            self.log(self.mem, "login", at(d, h, mm))
            self.log(self.mem, "logout", at(d, 17, 0))
        self.as_user(self.mem)
        res = self.client.get("/api/hr/attendance/mine/?month=2026-11")
        self.assertEqual(res.data["summary"], {"days": 2, "late_days": 1, "hours": 15.5, "open_days": 0})
        self.assertEqual(self.client.get("/api/hr/attendance/mine/?month=bad").status_code, 400)
        self.assertEqual(self.client.get("/api/hr/attendance/mine/?month=2026-13").status_code, 400)
        self.assertEqual(self.client.get("/api/hr/attendance/mine/?month=2026-10").data["rows"], [])

    def test_report_access_matrix(self):
        q = "?from=2026-11-01&to=2026-11-07"
        self.assert_matrix("get", "/api/hr/attendance/" + q, {"ceo": 200, "hr_head": 200, "hr_member": 200, "*": 403})
        self.assert_matrix("get", "/api/hr/attendance/export/" + q, {"ceo": 200, "hr_head": 200, "hr_member": 200, "*": 403})
        self.assert_matrix("get", "/api/hr/people/", {"ceo": 200, "hr_head": 200, "hr_member": 200, "*": 403})

    def test_report_filters_range_and_csv(self):
        a, b = self.mem, self.users["marketing"]
        self.log(a, "login", at(self.day, 9, 0))
        self.log(b, "login", at(self.day, 10, 0))
        self.as_user(self.hrm)
        base = "/api/hr/attendance/?from=2026-11-01&to=2026-11-07"
        res = self.client.get(base)
        self.assertEqual((res.data["count"], res.data["summary"]["late_days"]), (2, 1))
        self.assertEqual([r["user"] for r in self.client.get(base + "&late=1").data["results"]], [b.pk])
        self.assertEqual([r["user"] for r in self.client.get(base + f"&user={a.pk}").data["results"]], [a.pk])
        self.assertEqual(self.client.get(base + "&department=Marketing").data["count"], 1)
        self.assertEqual(self.client.get("/api/hr/attendance/?from=2026-11-07&to=2026-11-01").status_code, 400)
        self.assertEqual(self.client.get("/api/hr/attendance/?from=2026-01-01&to=2026-12-31").status_code, 400)
        self.assertEqual(self.client.get("/api/hr/attendance/?from=nope").status_code, 400)
        csv = self.client.get("/api/hr/attendance/export/?from=2026-11-01&to=2026-11-07")
        text = csv.content.decode("utf-8-sig")
        self.assertIn("Name,Department,Date", text)
        self.assertEqual(len(text.strip().splitlines()), 3)
        self.assertTrue(csv["Content-Disposition"].startswith("attachment"))

    def test_csv_neutralises_formulas_in_names(self):
        evil = self.make_user("evil@x.com", "Operation")
        evil.full_name = "=HYPERLINK(\"http://x\")"
        evil.save()
        self.log(evil, "login", at(self.day, 9, 0))
        self.as_user(self.hrh)
        text = self.client.get("/api/hr/attendance/export/?from=2026-11-01&to=2026-11-07").content.decode("utf-8-sig")
        self.assertIn("'=HYPERLINK", text)
        self.assertNotIn(",=HYPERLINK", text)
        self.assertNotIn("\n=HYPERLINK", text)

    def test_deactivated_people_leave_the_report(self):
        self.log(self.mem, "login", at(self.day, 9, 0))
        self.mem.is_active = False
        self.mem.save()
        self.as_user(self.hrh)
        self.assertEqual(self.client.get("/api/hr/attendance/?from=2026-11-01&to=2026-11-07").data["count"], 0)


# ===================== leave =====================
class LeaveTests(HCase):
    def req(self, user=None, start=None, end=None, ltype=None, **extra):
        start = start or next_working_day(TODAY() + timedelta(days=7))
        end = end or start
        self.as_user(user or self.mem)
        body = {"leave_type": (ltype or self.annual).pk, "start_date": start.isoformat(), "end_date": end.isoformat(), **extra}
        return self.client.post("/api/hr/leave/", body, format="json")

    def test_default_types_exist(self):
        self.as_role("operation_member")
        names = [t["name_en"] for t in self.client.get("/api/hr/leave-types/").data]
        self.assertEqual(names, ["Annual leave", "Sick leave", "Unpaid leave"])

    def test_request_counts_working_days_only(self):
        mon = date(2026, 11, 2)  # a Monday; Friday and Saturday are the weekend
        self.assertEqual(mon.weekday(), 0)
        self.assertEqual(leave.working_days(mon, mon + timedelta(days=6)), 5)
        self.assertEqual(leave.working_days(date(2026, 11, 6), date(2026, 11, 7)), 0)
        res = self.req(start=next_working_day(TODAY() + timedelta(days=7)), end=next_working_day(TODAY() + timedelta(days=7)) + timedelta(days=6))
        self.assertEqual((res.status_code, res.data["days"], res.data["status"]), (201, 5, "pending"))

    def test_request_validation(self):
        s = next_working_day(TODAY() + timedelta(days=7))
        bad = [
            ({"leave_type": 9999}, "leave_type"), ({"leave_type": ""}, "leave_type"), ({"start_date": "x"}, "start_date"), ({"end_date": "x"}, "end_date"),
            ({"start_date": s.isoformat(), "end_date": (s - timedelta(days=1)).isoformat()}, "end_date"),
            ({"start_date": D(-31), "end_date": D(-31)}, "start_date"),
            ({"reason": "r" * 501}, "reason"),
        ]
        for over, field in bad:
            self.as_user(self.mem)
            body = {"leave_type": self.annual.pk, "start_date": s.isoformat(), "end_date": s.isoformat(), **over}
            res = self.client.post("/api/hr/leave/", body, format="json")
            self.assertEqual(res.status_code, 400, over)
            self.assertIn(field, res.data, over)
        fri = next(d for d in (TODAY() + timedelta(days=n) for n in range(7, 20)) if d.weekday() == 4)
        self.assertIn("start_date", self.req(start=fri, end=fri + timedelta(days=1)).data)  # only weekend days
        self.assertIn("end_date", self.req(start=date(TODAY().year, 12, 30) if TODAY().month < 12 else TODAY(), end=date(TODAY().year + 1, 1, 2)).data)
        self.assertIn("end_date", self.req(end=s + timedelta(days=400)).data)
        self.assertEqual(LeaveRequest.objects.count(), 0)

    def test_recent_past_is_allowed(self):
        past = next_working_day(TODAY() - timedelta(days=10))
        if past <= TODAY():
            self.assertEqual(self.req(start=past, ltype=self.unpaid).status_code, 201)

    def test_overlap_is_refused(self):
        s = next_working_day(TODAY() + timedelta(days=7))
        self.assertEqual(self.req(start=s, end=s + timedelta(days=3)).status_code, 201)
        res = self.req(start=s + timedelta(days=2), end=s + timedelta(days=5), ltype=self.unpaid)
        self.assertIn("start_date", res.data)
        self.assertEqual(self.req(user=self.hrm, start=s, end=s + timedelta(days=3)).status_code, 201)  # someone else can

    def test_balance_blocks_requests_and_approval(self):
        self.annual.annual_days = 3
        self.annual.save()
        s = next_working_day(TODAY() + timedelta(days=7))
        r1 = self.req(start=s, end=next_working_day(s + timedelta(days=1))).data  # two working days
        self.assertEqual((r1["status"], r1["days"]), ("pending", 2))
        s2 = next_working_day(s + timedelta(days=20))
        self.as_user(self.hrh)
        self.assertEqual(self.client.post(f"/api/hr/leave/{r1['id']}/approve/").status_code, 200)
        res = self.req(start=s2, end=next_working_day(s2 + timedelta(days=1)))  # two more would pass the allowance of three
        self.assertIn("leave_type", res.data)
        self.assertEqual(self.req(start=s2, end=s2).status_code, 201)  # one more fits exactly
        self.as_user(self.mem)
        bal = next(b for b in self.client.get("/api/hr/leave/balance/").data["balances"] if b["name_en"] == "Annual leave")
        self.assertEqual((bal["allowance"], bal["used"], bal["pending"], bal["remaining"]), (3, 2, 1, 1))

    def test_unlimited_type_has_no_remaining(self):
        self.req(ltype=self.unpaid)
        self.as_user(self.mem)
        bal = next(b for b in self.client.get("/api/hr/leave/balance/").data["balances"] if b["name_en"] == "Unpaid leave")
        self.assertEqual((bal["allowance"], bal["remaining"], bal["pending"]), (None, None, 1))

    def test_approval_race_over_balance(self):
        self.annual.annual_days = 2
        self.annual.save()
        a = self.req(start=next_working_day(TODAY() + timedelta(days=7)), end=next_working_day(TODAY() + timedelta(days=7), 1)).data
        # a second request that fits only while the first is still pending is created directly
        s = next_working_day(TODAY() + timedelta(days=30))
        b = LeaveRequest.objects.create(user=self.mem, leave_type=self.annual, start_date=s, end_date=s, days=2)
        self.as_user(self.hrh)
        self.assertEqual(self.client.post(f"/api/hr/leave/{a['id']}/approve/").status_code, 200)
        res = self.client.post(f"/api/hr/leave/{b.pk}/approve/")
        self.assertEqual((res.status_code, res.data["detail"]), (400, leave.MSG_BALANCE))

    def test_decision_matrix(self):
        r = self.req().data
        pk = r["id"]
        for key, code in (("hr_head", 200), ("ceo", 403), ("hr_member", 403), ("commercial_head", 404), ("operation_member", 404), ("marketing", 404), ("commercial_member", 403)):
            row = LeaveRequest.objects.create(user=self.mem, leave_type=self.unpaid, start_date=TODAY() + timedelta(days=100 + len(key)), end_date=TODAY() + timedelta(days=100 + len(key)), days=1)
            self.as_role(key)
            self.assertEqual(self.client.post(f"/api/hr/leave/{row.pk}/approve/").status_code, code, key)

    def test_head_cannot_decide_own_and_ceo_decides_the_hr_head(self):
        mine = self.req(user=self.hrh).data
        self.as_user(self.hrh)
        self.assertEqual(self.client.post(f"/api/hr/leave/{mine['id']}/approve/").status_code, 403)
        self.as_user(self.hrm)
        self.assertEqual(self.client.post(f"/api/hr/leave/{mine['id']}/approve/").status_code, 403)
        self.as_user(self.ceo)
        self.assertEqual(self.client.post(f"/api/hr/leave/{mine['id']}/approve/").status_code, 200)

    def test_reject_needs_a_note_and_is_final(self):
        pk = self.req().data["id"]
        self.as_user(self.hrh)
        self.assertEqual(self.client.post(f"/api/hr/leave/{pk}/reject/", {"note": " "}, format="json").data["note"], leave.MSG_NOTE)
        res = self.client.post(f"/api/hr/leave/{pk}/reject/", {"note": "Busy season"}, format="json")
        self.assertEqual((res.data["status"], res.data["decision_note"], res.data["decided_by_name"]), ("rejected", "Busy season", self.hrh.full_name))
        for path in ("approve", "reject"):
            self.assertEqual(self.client.post(f"/api/hr/leave/{pk}/{path}/", {"note": "x"}, format="json").data["detail"], leave.MSG_STATE)
        n = Notification.objects.get(user=self.mem, kind="leave_rejected")
        self.assertIn("Busy season", n.body)

    def test_notifications_to_decider_and_requester(self):
        pk = self.req().data["id"]
        self.assertEqual(Notification.objects.filter(user=self.hrh, kind="leave_requested").count(), 1)
        self.assertFalse(Notification.objects.filter(user=self.hrm, kind="leave_requested").exists())
        self.as_user(self.hrh)
        self.client.post(f"/api/hr/leave/{pk}/approve/")
        self.assertEqual(Notification.objects.filter(user=self.mem, kind="leave_approved").count(), 1)
        self.req(user=self.hrh, start=next_working_day(TODAY() + timedelta(days=40)))
        self.assertEqual(Notification.objects.filter(user=self.ceo, kind="leave_requested").count(), 1)

    def test_ceo_cannot_request(self):
        self.assertEqual(self.req(user=self.ceo).status_code, 403)

    def test_cancel_rules(self):
        pk = self.req().data["id"]
        self.as_user(self.hrh)
        self.assertEqual(self.client.post(f"/api/hr/leave/{pk}/cancel/").status_code, 400)  # only the owner can cancel
        self.as_user(self.mem)
        self.assertEqual(self.client.post(f"/api/hr/leave/{pk}/cancel/").data["status"], "cancelled")
        self.assertEqual(self.client.post(f"/api/hr/leave/{pk}/cancel/").data["detail"], leave.MSG_STATE)
        again = self.req().data["id"]  # the dates are free again
        self.as_user(self.hrh)
        self.client.post(f"/api/hr/leave/{again}/approve/")
        self.as_user(self.mem)
        self.assertEqual(self.client.post(f"/api/hr/leave/{again}/cancel/").data["status"], "cancelled")  # approved but not started: allowed
        bal = next(b for b in self.client.get("/api/hr/leave/balance/").data["balances"] if b["name_en"] == "Annual leave")
        self.assertEqual(bal["used"], 0)  # the days come back
        started = LeaveRequest.objects.create(user=self.mem, leave_type=self.unpaid, start_date=TODAY(), end_date=TODAY() + timedelta(days=5), days=3, status="approved")
        self.assertEqual(self.client.post(f"/api/hr/leave/{started.pk}/cancel/").data["detail"], leave.MSG_STARTED)

    def test_list_scopes(self):
        mine = self.req().data["id"]
        other = self.req(user=self.hrm).data["id"]
        ids = lambda user, q: {r["id"] for r in (self.as_user(user) and self.client.get("/api/hr/leave/" + q)).data["results"]}
        self.assertEqual(ids(self.mem, ""), {mine})
        self.assertEqual(ids(self.hrm, ""), {other})
        self.assertEqual(ids(self.hrh, "?scope=all"), {mine, other})
        self.assertEqual(ids(self.hrh, "?scope=decide"), {mine, other})
        self.assertEqual(ids(self.ceo, "?scope=all"), {mine, other})
        self.assertEqual(ids(self.ceo, "?scope=decide"), set())  # the CEO only decides the HR head's
        self.as_user(self.mem)
        self.assertEqual(self.client.get("/api/hr/leave/?scope=all").status_code, 403)
        self.assertEqual(self.client.get("/api/hr/leave/?scope=decide").status_code, 403)
        self.as_user(self.hrm)
        self.assertEqual(self.client.get("/api/hr/leave/?scope=decide").data["count"], 0)
        self.as_user(self.mem)
        self.assertEqual(self.client.get(f"/api/hr/leave/{other}/").status_code, 404)

    def test_cannot_open_or_decide_other_peoples_requests_when_not_hr(self):
        other = self.req(user=self.hrm).data["id"]
        self.as_user(self.mem)
        for p in ("approve", "reject", "cancel"):
            self.assertEqual(self.client.post(f"/api/hr/leave/{other}/{p}/", {"note": "x"}, format="json").status_code, 404, p)

    def test_balance_of_others_is_hr_only(self):
        self.as_user(self.mem)
        self.assertEqual(self.client.get(f"/api/hr/leave/balance/?user={self.hrm.pk}").status_code, 403)
        self.as_user(self.hrh)
        self.assertEqual(self.client.get(f"/api/hr/leave/balance/?user={self.mem.pk}").status_code, 200)
        self.assertEqual(self.client.get("/api/hr/leave/balance/?year=abc").status_code, 400)

    def test_calendar_visibility(self):
        s = next_working_day(TODAY() + timedelta(days=3))
        rows = {}
        for key in ("commercial_member", "commercial_head", "hr_member", "marketing"):
            u = self.users[key]
            row = LeaveRequest.objects.create(user=u, leave_type=self.annual, start_date=s, end_date=s, days=1, status="approved", reason=f"secret {key}")
            rows[key] = row
        LeaveRequest.objects.create(user=self.users["operation_member"], leave_type=self.annual, start_date=s, end_date=s, days=1, status="rejected", decision_note="n")
        month = s.strftime("%Y-%m")

        def seen(key):
            self.as_role(key)
            return {r["user"] for r in self.client.get(f"/api/hr/leave/calendar/?month={month}").data["results"]}

        everyone = {self.users[k].pk for k in rows}
        self.assertEqual(seen("ceo"), everyone)
        self.assertEqual(seen("hr_head"), everyone)
        self.assertEqual(seen("hr_member"), everyone)
        self.assertEqual(seen("commercial_head"), {self.users["commercial_head"].pk, self.users["commercial_member"].pk})  # own department
        self.assertEqual(seen("commercial_member"), {self.users["commercial_member"].pk})
        self.assertEqual(seen("operation_head"), set())
        self.assertEqual(seen("marketing"), {self.users["marketing"].pk})
        self.as_role("commercial_head")
        res = self.client.get(f"/api/hr/leave/calendar/?month={month}").data["results"]
        self.assertTrue(all(r["reason"] == "" for r in res if r["user"] != self.users["commercial_head"].pk))
        self.assertEqual(self.client.get("/api/hr/leave/calendar/?month=zzz").status_code, 400)

    def test_leave_types_management(self):
        body = {"name_en": "Study leave", "name_ar": "إجازة دراسية", "annual_days": 5, "paid": True}
        self.assert_matrix("post", "/api/hr/leave-types/", {"hr_head": 201, "*": 403}, data=body)
        t = LeaveType.objects.filter(name_en="Study leave").first()
        self.assert_matrix("patch", f"/api/hr/leave-types/{t.pk}/", {"hr_head": 200, "*": 403}, data={"annual_days": 6})
        self.as_user(self.hrh)
        for bad in ({"name_en": "", "name_ar": "x"}, {"name_en": "x", "name_ar": " "}, {"name_en": "x", "name_ar": "y", "annual_days": 0}, {"name_en": "x", "name_ar": "y", "annual_days": "abc"}, {"name_en": "x", "name_ar": "y", "annual_days": 500}):
            self.assertEqual(self.client.post("/api/hr/leave-types/", bad, format="json").status_code, 400, bad)
        self.client.patch(f"/api/hr/leave-types/{t.pk}/", {"is_active": False}, format="json")
        self.assertNotIn("Study leave", [x["name_en"] for x in self.client.get("/api/hr/leave-types/").data])
        self.assertIn("Study leave", [x["name_en"] for x in self.client.get("/api/hr/leave-types/?all=1").data])
        self.assertTrue(LeaveType.objects.filter(pk=t.pk).exists())  # switched off, never deleted

    def test_unlimited_allowance_can_be_set(self):
        self.as_user(self.hrh)
        t = LeaveType.objects.get(name_en="Annual leave")
        res = self.client.patch(f"/api/hr/leave-types/{t.pk}/", {"annual_days": ""}, format="json")
        self.assertIsNone(res.data["annual_days"])

    def test_database_constraints(self):
        base = dict(user=self.mem, leave_type=self.annual, status="pending")
        with self.assertRaises(IntegrityError), transaction.atomic():
            LeaveRequest.objects.create(start_date=TODAY() + timedelta(days=2), end_date=TODAY(), days=1, **base)
        with self.assertRaises(IntegrityError), transaction.atomic():
            LeaveRequest.objects.create(start_date=TODAY(), end_date=TODAY(), days=0, **base)
        with self.assertRaises(IntegrityError), transaction.atomic():
            LeaveRequest.objects.create(start_date=TODAY(), end_date=TODAY(), days=1, user=self.mem, leave_type=self.annual, status="rejected")


# ===================== salaries, payroll, payslips =====================
SECRET = {"mem": "4321.55", "hrm": "2999.10"}


class PayrollCase(HCase):
    def setUp(self):
        super().setUp()
        self.month = TODAY().strftime("%Y-%m")
        self.hrh_salary = "5555.00"

    def salaries(self):
        for u, amount in ((self.mem, SECRET["mem"]), (self.hrm, SECRET["hrm"]), (self.hrh, self.hrh_salary)):
            self.as_user(self.hrh)
            res = self.client.put(f"/api/hr/salaries/{u.pk}/", {"base_salary": amount, "currency": "JOD"}, format="json")
            assert res.status_code == 200, res.data

    def mkrun(self):
        self.salaries()
        self.as_user(self.hrh)
        res = self.client.post("/api/hr/payroll/runs/", {"month": self.month}, format="json")
        assert res.status_code == 201, res.data
        return PayrollRun.objects.get(pk=res.data["id"])

    def entry(self, run, user):
        return run.entries.get(user=user)

    def go(self, user, method, path, data=None):
        self.as_user(user)
        if method == "get":
            return self.client.get(path, data)
        return getattr(self.client, method)(path, data or {}, format="json")


class SalaryTests(PayrollCase):
    def test_access_matrix(self):
        self.assert_matrix("get", "/api/hr/salaries/", {"ceo": 200, "hr_head": 200, "*": 403})
        self.assert_matrix("put", f"/api/hr/salaries/{self.mem.pk}/", {"hr_head": 200, "*": 403}, data={"base_salary": "100"})

    def test_set_validate_and_list(self):
        self.as_user(self.hrh)
        for bad in ({"base_salary": "-1"}, {"base_salary": "abc"}, {"base_salary": "NaN"}, {"base_salary": ""}, {"base_salary": "1", "currency": "JODD"}):
            self.assertEqual(self.client.put(f"/api/hr/salaries/{self.mem.pk}/", bad, format="json").status_code, 400, bad)
        self.assertEqual(self.client.put("/api/hr/salaries/99999/", {"base_salary": "1"}, format="json").status_code, 404)
        self.client.put(f"/api/hr/salaries/{self.mem.pk}/", {"base_salary": "700.5"}, format="json")
        self.client.put(f"/api/hr/salaries/{self.mem.pk}/", {"base_salary": "800"}, format="json")
        self.assertEqual(EmployeeSalary.objects.get(user=self.mem).base_salary, Decimal("800.00"))
        rows = {r["user"]: r for r in self.client.get("/api/hr/salaries/").data}
        self.assertEqual(rows[self.mem.pk]["base_salary"], "800.00")
        self.assertIsNone(rows[self.hrm.pk]["base_salary"])

    def test_salary_changes_are_audited_without_amounts(self):
        self.salaries()
        self.as_user(self.hrh)
        self.client.put(f"/api/hr/salaries/{self.mem.pk}/", {"base_salary": "9876.54"}, format="json")
        actions = list(AuditEntry.objects.filter(action__startswith="salary").values_list("action", flat=True))
        self.assertIn("salary_changed", actions)
        blob = json.dumps(list(AuditEntry.objects.values()), default=str)
        self.assertNotIn("9876", blob)


class RunTests(PayrollCase):
    def test_access_matrix(self):
        run = self.mkrun()
        read = {"ceo": 200, "hr_head": 200, "*": 403}
        self.assert_matrix("get", "/api/hr/payroll/runs/", read)
        self.assert_matrix("get", f"/api/hr/payroll/runs/{run.pk}/", read)
        self.assert_matrix("get", f"/api/hr/payroll/runs/{run.pk}/export/", read)
        self.assert_matrix("post", "/api/hr/payroll/runs/", {"hr_head": 400, "*": 403}, data={"month": self.month})  # head allowed; the month is taken
        self.assert_matrix("post", f"/api/hr/payroll/runs/{run.pk}/refresh/", {"hr_head": 200, "*": 403})
        e = self.entry(run, self.mem)
        self.assert_matrix("patch", f"/api/hr/payroll/entries/{e.pk}/", {"hr_head": 200, "*": 403}, data={"allowances": "1"})
        self.assert_matrix("post", f"/api/hr/payroll/runs/{run.pk}/approve/", {"ceo": 200, "*": 403}, data={})

    def test_create_validation(self):
        self.as_user(self.hrh)
        self.assertEqual(self.client.post("/api/hr/payroll/runs/", {"month": self.month}, format="json").data["detail"], payroll.MSG_NO_SALARIES)
        self.salaries()
        for bad, field in (({"month": ""}, "month"), ({"month": "x"}, "month"), ({"month": "2026-13"}, "month"), ({"month": "2999-01"}, "month")):
            self.assertIn(field, self.client.post("/api/hr/payroll/runs/", bad, format="json").data, bad)
        EmployeeSalary.objects.filter(user=self.hrm).update(currency="USD")
        self.assertEqual(self.client.post("/api/hr/payroll/runs/", {"month": self.month}, format="json").data["detail"], payroll.MSG_MIXED)
        EmployeeSalary.objects.filter(user=self.hrm).update(currency="JOD")
        ok = self.client.post("/api/hr/payroll/runs/", {"month": self.month + "-15"}, format="json")  # only year-month matters
        self.assertEqual((ok.status_code, ok.data["status"], ok.data["people"]), (201, "draft", 3))
        self.assertIn("month", self.client.post("/api/hr/payroll/runs/", {"month": self.month}, format="json").data)  # one run per month

    def test_inactive_people_are_not_paid(self):
        self.salaries()
        self.mem.is_active = False
        self.mem.save()
        self.as_user(self.hrh)
        res = self.client.post("/api/hr/payroll/runs/", {"month": self.month}, format="json")
        self.assertEqual(res.data["people"], 2)

    def test_entries_are_edited_in_draft_only(self):
        run = self.mkrun()
        e = self.entry(run, self.mem)
        self.as_user(self.hrh)
        res = self.client.patch(f"/api/hr/payroll/entries/{e.pk}/", {"allowances": "100", "deductions": "50.25", "note": "Bonus"}, format="json")
        self.assertEqual((res.data["net"], res.data["note"]), ("4371.30", "Bonus"))
        for bad, field in (({"allowances": "-1"}, "allowances"), ({"deductions": "x"}, "deductions"), ({"deductions": "999999"}, "deductions"), ({"note": "n" * 301}, "note")):
            self.assertIn(field, self.client.patch(f"/api/hr/payroll/entries/{e.pk}/", bad, format="json").data, bad)
        self.assertEqual(self.client.patch("/api/hr/payroll/entries/99999/", {}, format="json").status_code, 404)
        self.go(self.ceo, "post", f"/api/hr/payroll/runs/{run.pk}/approve/")
        res = self.go(self.hrh, "patch", f"/api/hr/payroll/entries/{e.pk}/", {"allowances": "1"})
        self.assertEqual((res.status_code, res.data["detail"]), (400, payroll.MSG_STATE))
        self.assertEqual(self.go(self.hrh, "post", f"/api/hr/payroll/runs/{run.pk}/refresh/").status_code, 400)

    def test_refresh_adds_new_people_and_updates_base_keeping_adjustments(self):
        run = self.mkrun()
        e = self.entry(run, self.mem)
        self.go(self.hrh, "patch", f"/api/hr/payroll/entries/{e.pk}/", {"allowances": "10"})
        newbie = self.make_user("new@x.com", "Operation")
        self.go(self.hrh, "put", f"/api/hr/salaries/{newbie.pk}/", {"base_salary": "600"})
        self.go(self.hrh, "put", f"/api/hr/salaries/{self.mem.pk}/", {"base_salary": "5000"})
        res = self.go(self.hrh, "post", f"/api/hr/payroll/runs/{run.pk}/refresh/")
        names = {x["user"]: x for x in res.data["entries"]}
        self.assertIn(newbie.pk, names)
        self.assertEqual((names[self.mem.pk]["base_salary"], names[self.mem.pk]["allowances"], names[self.mem.pk]["net"]), ("5000.00", "10.00", "5010.00"))

    def test_full_flow_and_state_rules(self):
        run = self.mkrun()
        url = lambda a: f"/api/hr/payroll/runs/{run.pk}/{a}/"
        self.assertEqual(self.go(self.hrh, "post", url("pay")).data["detail"], payroll.MSG_STATE)  # not approved yet
        self.assertEqual(self.go(self.ceo, "post", url("reopen"), {"reason": "x"}).data["detail"], payroll.MSG_STATE)
        self.assertEqual(self.go(self.hrh, "post", url("approve")).status_code, 403)
        res = self.go(self.ceo, "post", url("approve"))
        self.assertEqual((res.data["status"], res.data["approved_by_name"]), ("ceo_approved", self.ceo.full_name))
        self.assertEqual(self.go(self.ceo, "post", url("approve")).data["detail"], payroll.MSG_STATE)
        self.assertEqual(self.go(self.ceo, "post", url("pay")).status_code, 403)
        self.assertEqual(self.go(self.ceo, "post", url("reopen"), {"reason": " "}).data["reason"], payroll.MSG_REASON)
        self.assertEqual(self.go(self.ceo, "post", url("reopen"), {"reason": "Wrong bonus"}).data["status"], "draft")
        self.assertTrue(Notification.objects.filter(user=self.hrh, kind="payroll_reopened").exists())
        self.go(self.ceo, "post", url("approve"))
        self.assertTrue(Notification.objects.filter(user=self.hrh, kind="payroll_approved").exists())
        res = self.go(self.hrh, "post", url("pay"))
        self.assertEqual((res.data["status"], res.data["paid_by_name"]), ("paid", self.hrh.full_name))
        for a, who in (("approve", self.ceo), ("pay", self.hrh), ("refresh", self.hrh)):
            self.assertEqual(self.go(who, "post", url(a)).status_code, 400, a)
        self.assertEqual(self.go(self.ceo, "post", url("reopen"), {"reason": "x"}).data["detail"], payroll.MSG_STATE)  # paid is final
        self.assertEqual(set(Notification.objects.filter(kind="payslip_ready").values_list("user_id", flat=True)), {self.mem.pk, self.hrm.pk, self.hrh.pk})
        self.go(self.hrh, "post", url("pay"))
        self.assertEqual(Notification.objects.filter(kind="payslip_ready").count(), 3)  # never twice

    def test_run_permissions_flags(self):
        run = self.mkrun()
        self.assertEqual(self.go(self.hrh, "get", f"/api/hr/payroll/runs/{run.pk}/").data["permissions"], {"can_edit": True, "can_approve": False, "can_reopen": False, "can_pay": False})
        self.assertEqual(self.go(self.ceo, "get", f"/api/hr/payroll/runs/{run.pk}/").data["permissions"], {"can_edit": False, "can_approve": True, "can_reopen": False, "can_pay": False})

    def test_totals_and_csv(self):
        run = self.mkrun()
        res = self.go(self.hrh, "get", "/api/hr/payroll/runs/")
        self.assertEqual(res.data["results"][0]["total_net"], "12875.65")
        text = self.go(self.ceo, "get", f"/api/hr/payroll/runs/{run.pk}/export/").content.decode("utf-8-sig")
        self.assertIn("4321.55", text)

    def test_database_constraints(self):
        run = self.mkrun()
        e = self.entry(run, self.mem)
        for fields in ({"allowances": Decimal("-1")}, {"net": Decimal("1")}, {"deductions": Decimal("999999"), "net": Decimal("0")}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                PayrollEntry.objects.filter(pk=e.pk).update(**fields)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PayrollEntry.objects.create(run=run, user=self.mem, base_salary=1, net=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PayrollRun.objects.create(month=date(2020, 1, 2), created_by=self.hrh)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PayrollRun.objects.filter(pk=run.pk).update(status="paid")

    def test_my_work(self):
        run = self.mkrun()
        kinds = lambda user: [i["kind"] for i in self.go(user, "get", "/api/my-work/").data["items"] if i["kind"].startswith("payroll")]
        self.assertEqual(kinds(self.ceo), ["payroll_approve"])
        self.assertEqual(kinds(self.hrh), [])
        self.go(self.ceo, "post", f"/api/hr/payroll/runs/{run.pk}/approve/")
        self.assertEqual(kinds(self.ceo), [])
        self.assertEqual(kinds(self.hrh), ["payroll_pay"])
        self.assertEqual(kinds(self.mem), [])


class PayslipTests(PayrollCase):
    def paid_run(self):
        run = self.mkrun()
        self.go(self.hrh, "patch", f"/api/hr/payroll/entries/{self.entry(run, self.mem).pk}/", {"allowances": "50", "deductions": "20"})
        self.go(self.ceo, "post", f"/api/hr/payroll/runs/{run.pk}/approve/")
        return run

    def test_nothing_before_paid(self):
        run = self.paid_run()
        self.assertEqual(self.go(self.mem, "get", "/api/hr/payslips/").data, [])
        self.go(self.hrh, "post", f"/api/hr/payroll/runs/{run.pk}/pay/")
        res = self.go(self.mem, "get", "/api/hr/payslips/").data
        self.assertEqual(len(res), 1)
        self.assertEqual((res[0]["base_salary"], res[0]["allowances"], res[0]["deductions"], res[0]["net"], res[0]["month"]), ("4321.55", "50.00", "20.00", "4351.55", self.month))

    def test_only_own_payslip(self):
        run = self.paid_run()
        self.go(self.hrh, "post", f"/api/hr/payroll/runs/{run.pk}/pay/")
        mine = self.entry(run, self.mem).pk
        theirs = self.entry(run, self.hrm).pk
        self.assertEqual(self.go(self.mem, "get", f"/api/hr/payslips/{mine}/").status_code, 200)
        for user in (self.mem, self.hrh, self.ceo, self.users["operation_head"]):
            self.assertEqual(self.go(user, "get", f"/api/hr/payslips/{theirs}/").status_code, 200 if user == self.hrm else 404, user.email)
        self.assertEqual(self.go(self.hrm, "get", f"/api/hr/payslips/{theirs}/").status_code, 200)
        for key in ALL_ROLES:
            res = self.go(self.users[key], "get", "/api/hr/payslips/")
            self.assertEqual(res.status_code, 200)
            self.assertTrue(all(p["user_name"] == self.users[key].full_name for p in res.data), key)

    def test_a_person_without_a_salary_sees_an_empty_list(self):
        run = self.paid_run()
        self.go(self.hrh, "post", f"/api/hr/payroll/runs/{run.pk}/pay/")
        self.assertEqual(self.go(self.users["marketing"], "get", "/api/hr/payslips/").data, [])


class SalaryPrivacyTests(PayrollCase):
    """The figures must never turn up anywhere except the payroll endpoints they belong to."""

    def test_salary_figures_leak_nowhere(self):
        run = self.mkrun()
        self.go(self.hrh, "patch", f"/api/hr/payroll/entries/{self.entry(run, self.mem).pk}/", {"allowances": "123.45", "deductions": "67.89", "note": "adjust"})
        self.go(self.hrh, "post", f"/api/hr/payroll/runs/{run.pk}/refresh/")
        self.go(self.ceo, "post", f"/api/hr/payroll/runs/{run.pk}/approve/")
        self.go(self.ceo, "post", f"/api/hr/payroll/runs/{run.pk}/reopen/", {"reason": "check"})
        self.go(self.ceo, "post", f"/api/hr/payroll/runs/{run.pk}/approve/")
        self.go(self.hrh, "post", f"/api/hr/payroll/runs/{run.pk}/pay/")
        needles = ["4321", "2999", "5555", "123.45", "67.89", "4376", "4321.55"]

        # 1. Every text stored in the history, notifications and the sign-in log
        stored = json.dumps(list(AuditEntry.objects.values()), default=str) + json.dumps(list(Notification.objects.values("title", "body", "link", "kind")), default=str)
        stored += json.dumps(list(ActionLog.objects.values("action", "ip_address")), default=str)
        for n in needles:
            self.assertNotIn(n, stored, n)

        # 2. Every endpoint outside payroll, for every role
        urls = ["/api/auth/me/", "/api/users/", "/api/my-work/", "/api/notifications/", "/api/clients/", "/api/dashboard/", f"/api/activity/?target=payroll_run:{run.pk}",
                f"/api/comments/?target=payroll_run:{run.pk}", "/api/hr/attendance/mine/", "/api/hr/leave/?scope=all", "/api/hr/people/", "/api/hr/leave/balance/"]
        for key in ALL_ROLES:
            self.as_role(key)
            for url in urls:
                res = self.client.get(url)
                if res.status_code == 200 and hasattr(res, "content"):
                    body = res.content.decode("utf-8", "ignore")
                    for n in needles:
                        self.assertNotIn(n, body, f"{key} {url} leaked {n}")

    def test_run_history_is_viewable_only_by_ceo_and_hr_head_and_has_no_amounts(self):
        run = self.mkrun()
        self.go(self.hrh, "patch", f"/api/hr/payroll/entries/{self.entry(run, self.mem).pk}/", {"allowances": "12.34"})
        self.assert_matrix("get", f"/api/activity/?target=payroll_run:{run.pk}", {"ceo": 200, "hr_head": 200, "*": 404})
        self.as_user(self.ceo)
        self.assertNotIn("12.34", json.dumps(self.client.get(f"/api/activity/?target=payroll_run:{run.pk}").data, default=str))

    def test_salary_is_not_a_user_field(self):
        self.salaries()
        self.as_user(self.ceo)
        for url in ("/api/users/", "/api/auth/me/"):
            body = self.client.get(url).content.decode()
            self.assertNotIn("salary", body.lower(), url)

    def test_my_work_never_carries_figures(self):
        self.mkrun()
        self.as_user(self.ceo)
        self.assertNotIn("4321", self.client.get("/api/my-work/").content.decode())
