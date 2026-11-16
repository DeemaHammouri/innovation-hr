"""Objective 23, part 2: allowed and denied tests for the capabilities that rules consult (not endpoints).

Each test builds a role from an exact capability set, so the only difference between the allowed and the denied person is the one capability
under test. Allowed: the thing works (200/201, the record is listed, the report is served). Denied: a 403/404, an absent record or section,
and the stored data unchanged.

Covered: operation.work, operation.review, operation.view_all_clients, operation.view_own_deals, payment.manage, report.funnel,
report.revenue, report.forecast, report.operations, report.hr, hr.staff, hr.manage, hr.leave_request, hr.leave_decide_hr_head,
hr.payroll_approve.
"""
from datetime import timedelta

from django.utils import timezone

from accounts.catalog import CAPABILITIES
from accounts.models import Capability, Role, User
from core.testing import PASSWORD
from hr import access as hr_access
from hr.models import LeaveRequest, PayrollRun
from operations.models import TaskInstance
from operations.tests_lifecycle import LCase
from payments.models import Instalment

TODAY = lambda: timezone.localdate()


class Mixin:
    """Roles built from exact capability sets."""

    def person(self, caps, dept="Commercial", tag=None):
        caps = sorted(set(caps))
        key = tag or "p%d" % (len(User.objects.all()) + 1)
        role = Role.objects.create(key=key, name_en=key, name_ar=key)
        role.capabilities.set(Capability.objects.filter(code__in=caps))
        self.assertEqual(set(role.capabilities.values_list("code", flat=True)), set(caps), "unknown capability in the test role")
        return User.objects.create_user(email=f"{key}@x.com", password=PASSWORD, full_name=key, department=self.depts[dept], role_ref=role)

    def all_but(self, *dropped):
        return [c for c in CAPABILITIES if c not in dropped]


# ======================================================== Operation
class OperationRuleCapabilityTests(Mixin, LCase):
    def ids(self, user, url="/api/operations/clients/"):
        self.as_user(user)
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        return {r["id"] for r in res.data["results"]}

    def test_operation_view_all_clients_allowed_and_denied(self):
        loose, deal = self.mkclient(), self.mkclient(owner=self.cmem)
        allowed = self.person(["operation.access", "operation.view_all_clients"], "Operation")
        denied = self.person(["operation.access"], "Operation")
        self.assertEqual(self.ids(allowed), {loose.pk, deal.pk})
        self.assertEqual(self.client.get(f"/api/operations/clients/{loose.pk}/").status_code, 200)
        self.assertEqual(self.ids(denied), set())  # refused: nothing is listed
        self.assertEqual(self.client.get(f"/api/operations/clients/{loose.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/operations/tasks/?client={loose.pk}").data["count"], 0)

    def test_operation_view_own_deals_allowed_and_denied(self):
        allowed = self.person(["operation.access", "operation.view_own_deals"], "Commercial")
        denied = self.person(["operation.access"], "Commercial")
        mine, theirs = self.mkclient(owner=allowed), self.mkclient(owner=self.cmem)
        own_but_denied = self.mkclient(owner=denied)
        self.assertEqual(self.ids(allowed), {mine.pk})  # own deals only, never the other person's
        self.assertEqual(self.client.get(f"/api/operations/clients/{mine.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/operations/clients/{theirs.pk}/").status_code, 404)
        self.assertEqual(self.ids(denied), set())  # their own deal is invisible without operation.view_own_deals
        self.assertEqual(self.client.get(f"/api/operations/clients/{own_but_denied.pk}/").status_code, 404)

    def test_operation_work_allowed_and_denied(self):
        base = ["operation.access", "operation.view_all_clients"]
        worker = self.person(base + ["operation.work"], "Operation")
        onlooker = self.person(base, "Operation")
        mine, theirs = self.task(assignee=worker, due=TODAY()), self.task(assignee=onlooker, due=TODAY())
        res = self.do(worker, mine, "start")
        self.assertEqual((res.status_code, res.data["status"]), (200, "in_progress"))
        res = self.do(onlooker, theirs, "start")  # assigned to them, but they do not hold operation.work
        self.assertEqual(res.status_code, 403)
        self.assertEqual(self.status(theirs), "open")
        # the task list on My Work follows the same capability
        kinds = lambda u: [i["kind"] for i in (self.as_user(u), self.client.get("/api/my-work/"))[1].data["items"]]
        self.assertIn("op_task", kinds(worker))
        self.assertNotIn("op_task", kinds(onlooker))

    def test_operation_review_allowed_and_denied(self):
        base = ["operation.access", "operation.view_all_clients", "operation.work"]
        reviewer = self.person(base + ["operation.review"], "Operation")
        peer = self.person(base, "Operation")
        ok, no = self.task(assignee=self.omem), self.task(assignee=self.omem)
        TaskInstance.objects.filter(pk__in=[ok.pk, no.pk]).update(status="submitted")
        res = self.do(reviewer, ok, "approve")
        self.assertEqual((res.status_code, res.data["status"]), (200, "done"))
        self.assertEqual(self.do(peer, no, "approve").status_code, 403)
        self.assertEqual(self.do(peer, no, "return", {"comment": "No"}).status_code, 403)
        self.assertEqual(self.status(no), "submitted")  # untouched
        no.refresh_from_db()
        self.assertIsNone(no.reviewed_by_id)
        # the task payload tells each person whether they may review it
        self.as_user(reviewer)
        self.assertTrue(self.client.get(f"/api/operations/tasks/{no.pk}/").data["can_review"])
        self.as_user(peer)
        self.assertFalse(self.client.get(f"/api/operations/tasks/{no.pk}/").data["can_review"])


# ======================================================== Payments
class PaymentManageTests(Mixin, LCase):
    def sched(self, user, client):
        self.as_user(user)
        return self.client.post(f"/api/payments/clients/{client.pk}/schedule/", {"instalments": [{"due_date": (TODAY() + timedelta(days=9)).isoformat(), "amount": "10"}], "currency": "JOD"}, format="json")

    def test_payment_manage_allowed_and_denied(self):
        c1, c2, c3 = self.mkclient(), self.mkclient(), self.mkclient()
        manager = self.person(["payment.view", "payment.manage"], "Commercial")
        res = self.sched(manager, c1)
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["permissions"]["can_write"])
        inst = Instalment.objects.get(client=c1)
        self.assertEqual(self.client.post(f"/api/payments/instalments/{inst.pk}/payments/", {"amount": "4", "received_on": TODAY().isoformat(), "method": "cash"}, format="json").status_code, 201)
        # Roles that only hold related capabilities cannot write: payment.view alone, everything else but payment.manage, and the real CEO.
        viewer = self.person(["payment.view"], "Commercial")
        rich = self.person(self.all_but("payment.manage"), "Commercial")
        for who in (viewer, rich, self.ceo):
            self.assertEqual(self.sched(who, c2).status_code, 403, who.email)
            self.assertEqual(self.client.post(f"/api/payments/instalments/{inst.pk}/payments/", {"amount": "1", "received_on": TODAY().isoformat(), "method": "cash"}, format="json").status_code, 403, who.email)
            self.assertEqual(self.client.post(f"/api/payments/instalments/{inst.pk}/cancel/", {"reason": "x"}, format="json").status_code, 403, who.email)
            self.assertEqual(self.client.patch(f"/api/payments/instalments/{inst.pk}/", {"amount": "9"}, format="json").status_code, 403, who.email)
        self.assertFalse(Instalment.objects.filter(client=c2).exists())
        self.assertEqual(inst.payments.count(), 1)
        # they can still read, and the statement says they cannot write
        self.as_user(viewer)
        res = self.client.get(f"/api/payments/clients/{c1.pk}/")
        self.assertEqual((res.status_code, res.data["permissions"]["can_write"]), (200, False))
        # a role with payment.manage but no payment.view is refused too (the write needs the area)
        blind = self.person(["payment.manage"], "Commercial")
        self.assertEqual(self.sched(blind, c3).status_code, 403)

    def test_payment_manage_overdue_items_on_my_work(self):
        c = self.mkclient()
        manager = self.person(["payment.view", "payment.manage"], "Commercial")
        self.sched(manager, c)
        Instalment.objects.filter(client=c).update(due_date=TODAY() - timedelta(days=3))
        kinds = lambda u: [i["kind"] for i in (self.as_user(u), self.client.get("/api/my-work/"))[1].data["items"]]
        self.assertIn("payment_overdue", kinds(manager))
        self.assertNotIn("payment_overdue", kinds(self.person(["payment.view"], "Commercial")))


# ======================================================== Reports
class ReportCapabilityTests(Mixin, LCase):
    def check(self, section):
        code = f"report.{section}"
        allowed = self.person([code], "Commercial", tag=f"only_{section}")
        denied = self.person([c for c in CAPABILITIES if c.startswith("report.") and c != code], "Commercial", tag=f"not_{section}")
        self.as_user(allowed)
        res = self.client.get(f"/api/reports/{section}/")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn("period", res.data)
        self.assertEqual(self.client.get(f"/api/reports/{section}/export/").status_code, 200)
        self.assertEqual(self.client.get("/api/reports/").data["sections"], [section])
        self.as_user(denied)
        self.assertEqual(self.client.get(f"/api/reports/{section}/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/reports/{section}/export/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/reports/{section}/export/?fmt=xlsx").status_code, 403)
        self.assertNotIn(section, self.client.get("/api/reports/").data["sections"])

    def test_report_funnel_allowed_and_denied(self):
        self.assertIn("report.funnel", CAPABILITIES)
        self.check("funnel")

    def test_report_revenue_allowed_and_denied(self):
        self.assertIn("report.revenue", CAPABILITIES)
        self.check("revenue")

    def test_report_forecast_allowed_and_denied(self):
        self.assertIn("report.forecast", CAPABILITIES)
        self.check("forecast")

    def test_report_operations_allowed_and_denied(self):
        self.assertIn("report.operations", CAPABILITIES)
        self.check("operations")

    def test_report_hr_allowed_and_denied(self):
        self.assertIn("report.hr", CAPABILITIES)
        self.check("hr")


# ======================================================== HR
class HrRuleCapabilityTests(Mixin, LCase):
    def setUp(self):
        super().setUp()
        self.hrh, self.hrm, self.mem = self.users["hr_head"], self.users["hr_member"], self.users["commercial_member"]

    def leave_row(self, user, offset=40):
        d = TODAY() + timedelta(days=offset)
        return LeaveRequest.objects.create(user=user, leave_type=self.annual_type(), start_date=d, end_date=d, days=1)

    def annual_type(self):
        from hr.models import LeaveType
        return LeaveType.objects.get(name_en="Unpaid leave")

    def decide(self, user, row, action="approve"):
        self.as_user(user)
        return self.client.post(f"/api/hr/leave/{row.pk}/{action}/", {}, format="json")

    def test_hr_leave_request_allowed_and_denied(self):
        body = {"leave_type": self.annual_type().pk, "start_date": (TODAY() + timedelta(days=45)).isoformat(), "end_date": (TODAY() + timedelta(days=45)).isoformat()}
        # pick a working day so the request has days to count
        from hr import leave
        d = TODAY() + timedelta(days=45)
        while d.weekday() in leave.weekend():
            d += timedelta(days=1)
        body["start_date"] = body["end_date"] = d.isoformat()
        allowed = self.person(["hr.leave_request"], "Commercial")
        denied = self.person(self.all_but("hr.leave_request"), "Commercial")
        self.as_user(allowed)
        res = self.client.post("/api/hr/leave/", body, format="json")
        self.assertEqual((res.status_code, res.data["status"]), (201, "pending"))
        self.as_user(denied)
        self.assertEqual(self.client.post("/api/hr/leave/", body, format="json").status_code, 403)  # even holding every other capability
        self.assertEqual(LeaveRequest.objects.filter(user=denied).count(), 0)
        self.assertEqual(LeaveRequest.objects.filter(user=allowed).count(), 1)
        # the CEO holds no hr.leave_request by default and is refused the same way
        self.as_user(self.ceo)
        self.assertEqual(self.client.post("/api/hr/leave/", body, format="json").status_code, 403)

    def test_hr_manage_allowed_and_denied(self):
        see = ["hr.attendance_all"]
        head = self.person(see + ["hr.manage"], "HR")
        staff = self.person(see + self.all_but("hr.manage", "hr.leave_decide_hr_head", "hr.payroll_approve"), "HR")
        row_ok, row_no = self.leave_row(self.mem), self.leave_row(self.mem, 41)
        res = self.decide(head, row_ok)
        self.assertEqual((res.status_code, res.data["status"]), (200, "approved"))
        self.assertEqual(self.decide(staff, row_no).status_code, 403)  # sees it, but cannot decide it
        self.assertEqual(self.decide(staff, row_no, "reject").status_code, 403)
        row_no.refresh_from_db()
        self.assertEqual((row_no.status, row_no.decided_by_id), ("pending", None))
        # leave types and payroll are the HR head's too
        t = {"name_en": "Study", "name_ar": "دراسة", "annual_days": 5}
        self.as_user(head)
        self.assertEqual(self.client.post("/api/hr/leave-types/", t, format="json").status_code, 201)
        self.as_user(staff)
        self.assertEqual(self.client.post("/api/hr/leave-types/", {**t, "name_en": "Study 2"}, format="json").status_code, 403)
        self.assertFalse(self.annual_type().__class__.objects.filter(name_en="Study 2").exists())
        self.assertEqual(self.client.put(f"/api/hr/salaries/{self.mem.pk}/", {"base_salary": "1", "currency": "JOD"}, format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/hr/payroll/runs/", {"month": TODAY().strftime("%Y-%m")}, format="json").status_code, 403)
        self.assertFalse(PayrollRun.objects.exists())

    def test_hr_leave_decide_hr_head_allowed_and_denied(self):
        see = ["hr.attendance_all"]
        decider = self.person(see + ["hr.leave_decide_hr_head"], "Operation")
        manager = self.person(see + ["hr.manage", "hr.staff"], "HR")
        row_ok, row_no = self.leave_row(self.hrh), self.leave_row(self.hrh, 41)
        res = self.decide(decider, row_ok)
        self.assertEqual((res.status_code, res.data["status"]), (200, "approved"))
        self.assertEqual(self.decide(manager, row_no).status_code, 403)  # hr.manage decides everyone else's leave, not the HR head's
        self.assertEqual(self.decide(self.hrm, row_no).status_code, 403)
        row_no.refresh_from_db()
        self.assertEqual(row_no.status, "pending")
        # and the capability gives no power over an ordinary member's leave
        ordinary = self.leave_row(self.mem, 42)
        self.assertEqual(self.decide(decider, ordinary).status_code, 403)
        ordinary.refresh_from_db()
        self.assertEqual(ordinary.status, "pending")

    def test_hr_staff_allowed_and_denied(self):
        # hr.staff marks "HR work" (hr.access.is_hr). No endpoint consults it yet: it is a flag, so the proof is the rule itself,
        # plus the fact that it grants no decision or payroll power on its own (those are hr.manage / hr.payroll_approve).
        staff = self.person(["hr.staff"], "HR")
        other = self.person(self.all_but("hr.staff"), "HR")
        self.assertTrue(hr_access.is_hr(staff))
        self.assertFalse(hr_access.is_hr(other))
        row = self.leave_row(self.mem)
        self.assertEqual(self.decide(staff, row).status_code, 404)  # not even visible: attendance_all is a different capability
        staff2 = self.person(["hr.staff", "hr.attendance_all"], "HR")
        self.assertEqual(self.decide(staff2, row).status_code, 403)  # visible, still cannot decide
        self.as_user(staff2)
        self.assertEqual(self.client.get("/api/hr/payroll/runs/").status_code, 403)
        row.refresh_from_db()
        self.assertEqual(row.status, "pending")

    def test_hr_payroll_approve_allowed_and_denied(self):
        self.as_user(self.hrh)
        for u in (self.mem, self.hrm):
            self.assertEqual(self.client.put(f"/api/hr/salaries/{u.pk}/", {"base_salary": "900", "currency": "JOD"}, format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/hr/payroll/runs/", {"month": TODAY().strftime("%Y-%m")}, format="json").status_code, 201)
        run = PayrollRun.objects.get()
        url = lambda a: f"/api/hr/payroll/runs/{run.pk}/{a}/"
        approver = self.person(["hr.payroll_view", "hr.payroll_approve"], "Operation", tag="approver")
        viewer = self.person(["hr.payroll_view"], "Operation", tag="viewer")
        head_like = self.person(["hr.payroll_view", "hr.manage", "hr.staff", "hr.attendance_all"], "HR", tag="headlike")
        everything = self.person(self.all_but("hr.payroll_approve"), "Operation", tag="everything")
        for who in (viewer, head_like, everything, self.hrh):
            self.as_user(who)
            self.assertEqual(self.client.post(url("approve"), {}, format="json").status_code, 403, who.email)
        run.refresh_from_db()
        self.assertEqual(run.status, "draft")
        self.assertIsNone(run.approved_by_id)
        self.as_user(approver)
        res = self.client.post(url("approve"), {}, format="json")
        self.assertEqual((res.status_code, res.data["status"]), (200, "ceo_approved"))
        # reopening is the same capability
        for who in (viewer, head_like, everything, self.hrh):
            self.as_user(who)
            self.assertEqual(self.client.post(url("reopen"), {"reason": "x"}, format="json").status_code, 403, who.email)
        run.refresh_from_db()
        self.assertEqual(run.status, "ceo_approved")
        self.as_user(approver)
        self.assertEqual(self.client.post(url("reopen"), {"reason": "Wrong bonus"}, format="json").data["status"], "draft")
        # My Work shows the approver a payroll to approve, and nobody else
        kinds = lambda u: [i["kind"] for i in (self.as_user(u), self.client.get("/api/my-work/"))[1].data["items"]]
        self.assertIn("payroll_approve", kinds(approver))
        self.assertNotIn("payroll_approve", kinds(head_like))
