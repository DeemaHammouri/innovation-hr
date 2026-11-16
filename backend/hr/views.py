from calendar import monthrange
from datetime import date, timedelta

from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import PasswordChangeNotPending
from core.csvout import csv_response
from core.pagination import StandardPagination
from leads.sla import sla_now

from . import access, attendance, leave, payroll
from .models import EmployeeSalary, LeaveRequest, LeaveType, PayrollEntry, PayrollRun
from .serializers import EntrySerializer, LeaveRequestSerializer, LeaveTypeSerializer, PayslipSerializer, RunSerializer, SalarySerializer

MSG_HR_HEAD = "Only the HR head can do this."
MSG_CEO = "Only the CEO can do this."
MSG_NO_LEAVE = "The CEO doesn't request leave."
MSG_NO_PAYROLL = "You don't have access to payroll."
MSG_RANGE = "Choose a date range of up to 93 days."


class Authed:
    permission_classes = [IsAuthenticated, PasswordChangeNotPending]

    def today(self):
        return sla_now()[0]

    def ctx(self):
        return {"request": self.request, "today": self.today()}


def parse_day(raw, default):
    try:
        return date.fromisoformat(str(raw)[:10]) if raw else default
    except ValueError:
        raise ValidationError({"detail": "Choose valid dates."})


def parse_month(raw, today):
    try:
        y, m = str(raw).split("-") if raw else (today.year, today.month)
        first = date(int(y), int(m), 1)
    except (ValueError, TypeError):
        raise ValidationError({"detail": "Choose a month, like 2026-11."})
    return first, first.replace(day=monthrange(first.year, first.month)[1])


# ---------------- attendance ----------------
class AttendanceMineView(Authed, APIView):
    """GET /api/hr/attendance/mine/?month=2026-11 (&format=csv via /export/)."""

    def get(self, request):
        start, end = parse_month(request.query_params.get("month"), self.today())
        rows = attendance.rows_for([request.user], start, end)
        return Response({"month": start.strftime("%Y-%m"), "rows": rows, "summary": attendance.summary(rows), "work_hours": work_hours()})


def work_hours():
    from lookups.models import WorkHours

    w = WorkHours.get()
    return {"work_start": w.work_start.strftime("%H:%M"), "work_end": w.work_end.strftime("%H:%M"), "grace_minutes": w.grace_minutes}


def csv_rows(rows):
    return [[r["user_name"], r["department"], r["date"], r["first_in"].strftime("%H:%M"), r["last_out"].strftime("%H:%M") if r["last_out"] else "", r["hours"] if r["hours"] is not None else "", "late" if r["late"] else "on time", r["minutes_late"]] for r in rows]


CSV_HEADER = ["Name", "Department", "Date", "First sign-in", "Last sign-out", "Hours", "Status", "Minutes after work start"]


class AttendanceMineExportView(AttendanceMineView):
    def get(self, request):
        start, end = parse_month(request.query_params.get("month"), self.today())
        return csv_response(f"attendance-{start:%Y-%m}.csv", CSV_HEADER, csv_rows(attendance.rows_for([request.user], start, end)))


class AttendanceReportView(Authed, APIView):
    """GET /api/hr/attendance/?from=&to=&user=&late=1 - HR and the CEO only."""

    pagination_class = StandardPagination

    def rows(self, request):
        if not access.sees_everyone(request.user):
            raise PermissionDenied("You don't have access to the attendance report.")
        today = self.today()
        end = parse_day(request.query_params.get("to"), today)
        start = parse_day(request.query_params.get("from"), end - timedelta(days=6))
        if start > end or (end - start).days >= attendance.MAX_RANGE_DAYS:
            raise ValidationError({"detail": MSG_RANGE})
        people = attendance.employees()
        uid = request.query_params.get("user")
        if uid:
            people = people.filter(pk=int(uid) if uid.isdigit() else 0)
        dept = request.query_params.get("department")
        if dept:
            people = people.filter(department__name=dept)
        return start, end, attendance.rows_for(people, start, end, late_only=request.query_params.get("late") == "1")

    def get(self, request):
        start, end, rows = self.rows(request)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        res = paginator.get_paginated_response(page)
        res.data["summary"] = attendance.summary(rows)
        res.data["range"] = {"from": start, "to": end}
        return res


class AttendanceReportExportView(AttendanceReportView):
    def get(self, request):
        start, end, rows = self.rows(request)
        return csv_response(f"attendance-{start}-{end}.csv", CSV_HEADER, csv_rows(rows))


class PeopleView(Authed, APIView):
    """GET /api/hr/people/ - names for the report's filter. HR and the CEO."""

    def get(self, request):
        if not access.sees_everyone(request.user):
            raise PermissionDenied("You don't have access to the attendance report.")
        return Response([{"id": u.pk, "full_name": u.full_name, "department": u.department.name} for u in attendance.employees().order_by("full_name")])


# ---------------- leave ----------------
class LeaveTypeViewSet(Authed, viewsets.ViewSet):
    def list(self, request):
        qs = LeaveType.objects.all() if access.is_hr_head(request.user) and request.query_params.get("all") == "1" else LeaveType.objects.filter(is_active=True)
        return Response(LeaveTypeSerializer(qs, many=True).data)

    def create(self, request):
        if not access.is_hr_head(request.user):
            raise PermissionDenied(MSG_HR_HEAD)
        return Response(LeaveTypeSerializer(leave.save_type(request.user, request.data)).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        if not access.is_hr_head(request.user):
            raise PermissionDenied(MSG_HR_HEAD)
        t = get_object_or_404(LeaveType, pk=int(pk) if str(pk).isdigit() else 0)
        return Response(LeaveTypeSerializer(leave.save_type(request.user, request.data, t)).data)


class LeaveViewSet(Authed, viewsets.ViewSet):
    """/api/hr/leave/ - requests (mine / all / to decide), balance, calendar."""

    RELATED = ("user__department", "leave_type", "decided_by")

    def visible(self):
        u = self.request.user
        qs = LeaveRequest.objects.select_related(*self.RELATED)
        return qs if access.sees_everyone(u) else qs.filter(user=u)

    def get_req(self, pk):
        return get_object_or_404(self.visible(), pk=int(pk) if str(pk).isdigit() else 0)

    def list(self, request):
        scope = request.query_params.get("scope", "mine")
        qs = LeaveRequest.objects.select_related(*self.RELATED)
        if scope == "mine":
            qs = qs.filter(user=request.user)
        elif scope in ("all", "decide"):
            if not access.sees_everyone(request.user):
                raise PermissionDenied("You don't have access to everyone's leave requests.")
            if scope == "decide":
                qs = qs.filter(status="pending").exclude(user=request.user)
                if access.is_ceo(request.user):
                    qs = qs.filter(user__department__name="HR", user__is_dept_head=True)
                elif not access.is_hr_head(request.user):
                    qs = qs.none()
        if request.query_params.get("status"):
            qs = qs.filter(status__in=request.query_params["status"].split(","))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs.order_by("-start_date", "-id"), request, view=self)
        return paginator.get_paginated_response(LeaveRequestSerializer(page, many=True, context=self.ctx()).data)

    def create(self, request):
        if not access.can_request_leave(request.user):
            raise PermissionDenied(MSG_NO_LEAVE)
        req = leave.request_leave(request.user, request.data, self.today())
        return Response(LeaveRequestSerializer(LeaveRequest.objects.select_related(*self.RELATED).get(pk=req.pk), context=self.ctx()).data, status=status.HTTP_201_CREATED)

    def _decide(self, request, pk, fn, *args):
        req = self.get_req(pk)
        if not access.can_decide(request.user, req):
            raise PermissionDenied("You can't decide this request.")
        fn(request.user, req, *args)
        return Response(LeaveRequestSerializer(self.get_req(pk), context=self.ctx()).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._decide(request, pk, leave.approve)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._decide(request, pk, leave.reject, request.data.get("note"))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        req = self.get_req(pk)
        leave.cancel(request.user, req, self.today())
        return Response(LeaveRequestSerializer(self.get_req(pk), context=self.ctx()).data)

    @action(detail=False, methods=["get"])
    def balance(self, request):
        user = request.user
        who = request.query_params.get("user")
        if who:
            if not (access.sees_everyone(request.user)):
                raise PermissionDenied("You can only see your own balance.")
            user = get_object_or_404(User, pk=int(who) if who.isdigit() else 0, is_active=True)
        try:
            year = int(request.query_params.get("year") or self.today().year)
        except ValueError:
            raise ValidationError({"detail": "Choose a valid year."})
        return Response({"year": year, "balances": leave.balances(user, year)})

    @action(detail=False, methods=["get"])
    def calendar(self, request):
        start, end = parse_month(request.query_params.get("month"), self.today())
        qs = (LeaveRequest.objects.select_related(*self.RELATED).filter(leave.calendar_q(request.user), start_date__lte=end, end_date__gte=start)
              .exclude(status__in=["rejected", "cancelled"]).order_by("start_date", "user__full_name"))
        data = LeaveRequestSerializer(qs, many=True, context=self.ctx()).data
        if not access.sees_everyone(request.user):  # others see approved leave only, and never the reason
            data = [{**d, "reason": ""} for d in data if d["status"] == "approved" or d["user"] == request.user.pk]
        return Response({"month": start.strftime("%Y-%m"), "weekend_days": sorted(leave.weekend()), "results": data})


# ---------------- salaries, payroll, payslips ----------------
class PayrollBase(Authed):
    def need_see(self):
        if not access.sees_payroll(self.request.user):
            raise PermissionDenied(MSG_NO_PAYROLL)

    def need_manage(self):
        if not access.manages_payroll(self.request.user):
            raise PermissionDenied(MSG_HR_HEAD)

    def need_ceo(self):
        if not access.is_ceo(self.request.user):
            raise PermissionDenied(MSG_CEO)


def runs_qs():
    return PayrollRun.objects.select_related("approved_by", "paid_by").annotate(people=Count("entries"), net_total=Sum("entries__net"))


class SalaryViewSet(PayrollBase, viewsets.ViewSet):
    def list(self, request):
        self.need_see()
        have = {s.user_id: s for s in EmployeeSalary.objects.select_related("user__department")}
        out = []
        for u in attendance.employees().order_by("full_name"):
            s = have.get(u.pk)
            out.append({"user": u.pk, "user_name": u.full_name, "department": u.department.name, "base_salary": f"{s.base_salary:.2f}" if s else None, "currency": s.currency if s else None})
        return Response(out)

    def update(self, request, pk=None):
        self.need_manage()
        user = User.objects.filter(pk=int(pk) if str(pk).isdigit() else 0).first()
        if user is None:
            raise NotFound("Record not found.")
        s = payroll.set_salary(request.user, user, request.data)
        return Response(SalarySerializer(EmployeeSalary.objects.select_related("user__department").get(pk=s.pk)).data)


class RunViewSet(PayrollBase, viewsets.ViewSet):
    def get_run(self, pk):
        self.need_see()
        run = runs_qs().filter(pk=int(pk) if str(pk).isdigit() else 0).first()
        if run is None:
            raise NotFound("Record not found.")
        return run

    def out(self, pk, code=status.HTTP_200_OK):
        return Response(RunSerializer(runs_qs().get(pk=pk), context=self.ctx()).data, status=code)

    def list(self, request):
        self.need_see()
        paginator = StandardPagination()
        page = paginator.paginate_queryset(runs_qs(), request, view=self)
        return paginator.get_paginated_response(RunSerializer(page, many=True, context=self.ctx()).data)

    def create(self, request):
        self.need_manage()
        return self.out(payroll.create_run(request.user, request.data.get("month")).pk, status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        run = self.get_run(pk)
        entries = PayrollEntry.objects.filter(run=run).select_related("user__department")
        return Response({**RunSerializer(run, context=self.ctx()).data, "entries": EntrySerializer(entries, many=True).data})

    @action(detail=True, methods=["post"])
    def refresh(self, request, pk=None):
        self.need_manage()
        payroll.refresh(request.user, self.get_run(pk))
        return self.retrieve(request, pk)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        self.need_ceo()
        payroll.approve(request.user, self.get_run(pk))
        return self.retrieve(request, pk)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        self.need_ceo()
        payroll.reopen(request.user, self.get_run(pk), request.data.get("reason"))
        return self.retrieve(request, pk)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        self.need_manage()
        payroll.mark_paid(request.user, self.get_run(pk))
        return self.retrieve(request, pk)

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        run = self.get_run(pk)
        rows = [[e.user.full_name, e.user.department.name, e.base_salary, e.allowances, e.deductions, e.net, run.currency] for e in PayrollEntry.objects.filter(run=run).select_related("user__department")]
        return csv_response(f"payroll-{run.month:%Y-%m}.csv", ["Name", "Department", "Base salary", "Allowances", "Deductions", "Net", "Currency"], rows)


class EntryViewSet(PayrollBase, viewsets.ViewSet):
    def partial_update(self, request, pk=None):
        self.need_manage()
        entry = get_object_or_404(PayrollEntry.objects.select_related("run", "user__department"), pk=int(pk) if str(pk).isdigit() else 0)
        entry = payroll.update_entry(request.user, entry, request.data)
        return Response(EntrySerializer(PayrollEntry.objects.select_related("user__department").get(pk=entry.pk)).data)


class PayslipViewSet(Authed, viewsets.ViewSet):
    """A person's own payslips, once the run is paid. Nobody reads anyone else's through this route."""

    def qs(self):
        return PayrollEntry.objects.filter(user=self.request.user, run__status="paid").select_related("run", "user__department").order_by("-run__month")

    def list(self, request):
        return Response(PayslipSerializer(self.qs(), many=True).data)

    def retrieve(self, request, pk=None):
        return Response(PayslipSerializer(get_object_or_404(self.qs(), pk=int(pk) if str(pk).isdigit() else 0)).data)
