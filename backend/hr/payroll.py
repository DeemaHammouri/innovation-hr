"""
Payroll: a monthly run of one entry per employee. Draft (HR head edits) -> CEO approved (entries frozen) -> Paid (HR head).

Salary figures are never written to the activity trail, to notifications or to any log: audit lines say that something changed,
never the amount.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from audit.models import record
from notifications.service import notify

from .models import EmployeeSalary, PayrollEntry, PayrollRun

MSG_STATE = "That can't be done in the current state."
MSG_MONTH = "Choose a month, like 2026-11."
MSG_FUTURE = "You can't run payroll for a future month."
MSG_EXISTS = "There is already a payroll run for that month."
MSG_NO_SALARIES = "No employee has a salary on file yet. Add salaries first."
MSG_MIXED = "All salaries in one run must use the same currency."
MSG_AMOUNT = "Enter an amount of zero or more."
MSG_NET = "Deductions can't be more than the salary plus allowances."
MSG_NOTE_LONG = "Keep this under 300 characters."
MSG_REASON = "Write why you are sending this run back to draft."
MSG_EMPTY = "This run has no entries."
MSG_SALARY = "Enter a salary of zero or more."
MSG_PERSON = "Choose an employee."
MSG_CURRENCY = "Enter a 3-letter currency code, such as JOD."

TWO = Decimal("0.01")
MAX = Decimal("9999999999.99")
Status = PayrollRun.Status


def parse_month(raw):
    try:
        y, m = str(raw).strip()[:7].split("-")
        d = date(int(y), int(m), 1)
    except (ValueError, TypeError):
        raise ValidationError({"month": MSG_MONTH})
    if d > timezone.localdate().replace(day=1):
        raise ValidationError({"month": MSG_FUTURE})
    return d


def money(raw, message, field):
    try:
        v = Decimal(str(raw).strip()).quantize(TWO)
    except (InvalidOperation, ValueError, AttributeError):
        raise ValidationError({field: message})
    if not v.is_finite() or v < 0 or v > MAX:
        raise ValidationError({field: message})
    return v


def payable():
    return User.objects.filter(is_active=True, is_superuser=False, department__isnull=False)


# ---------- salary master ----------
def set_salary(actor, user, data):
    if user is None or not user.is_active or user.is_superuser or not user.department_id:
        raise ValidationError({"user": MSG_PERSON})
    base = money(data.get("base_salary"), MSG_SALARY, "base_salary")
    code = str(data.get("currency") or "JOD").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValidationError({"currency": MSG_CURRENCY})
    with transaction.atomic():
        sal, created = EmployeeSalary.objects.update_or_create(user=user, defaults={"base_salary": base, "currency": code, "updated_by": actor})
        record(actor, sal, "salary_set" if created else "salary_changed")  # never the amount
    return sal


# ---------- runs ----------
def _entry(run, sal):
    return PayrollEntry(run=run, user=sal.user, base_salary=sal.base_salary, allowances=0, deductions=0, net=sal.base_salary)


def create_run(actor, month_raw):
    month = parse_month(month_raw)
    sals = list(EmployeeSalary.objects.filter(user__in=payable()).select_related("user"))
    if not sals:
        raise ValidationError({"detail": MSG_NO_SALARIES})
    if len({s.currency for s in sals}) > 1:
        raise ValidationError({"detail": MSG_MIXED})
    with transaction.atomic():
        if PayrollRun.objects.filter(month=month).exists():
            raise ValidationError({"month": MSG_EXISTS})
        run = PayrollRun.objects.create(month=month, currency=sals[0].currency, created_by=actor)
        PayrollEntry.objects.bulk_create([_entry(run, s) for s in sals])
        record(actor, run, "created", to_value=month.strftime("%Y-%m"))
    return run


def _locked(run_id):
    return PayrollRun.objects.select_for_update().get(pk=run_id)


def refresh(actor, run):
    """Draft only: pick up new hires and current base salaries, keeping any allowances and deductions already entered."""
    with transaction.atomic():
        run = _locked(run.pk)
        if run.status != Status.DRAFT:
            raise ValidationError({"detail": MSG_STATE})
        sals = {s.user_id: s for s in EmployeeSalary.objects.filter(user__in=payable()).select_related("user")}
        if len({s.currency for s in sals.values()}) > 1:
            raise ValidationError({"detail": MSG_MIXED})
        have = {e.user_id: e for e in run.entries.all()}
        for uid, s in sals.items():
            if uid in have:
                e = have[uid]
                e.base_salary = s.base_salary
                e.net = e.base_salary + e.allowances - e.deductions
                if e.net < 0:
                    raise ValidationError({"detail": MSG_NET})
                e.save()
            else:
                PayrollEntry.objects.create(run=run, user=s.user, base_salary=s.base_salary, allowances=0, deductions=0, net=s.base_salary)
        record(actor, run, "refreshed")
    return run


def update_entry(actor, entry, data):
    with transaction.atomic():
        run = _locked(entry.run_id)
        if run.status != Status.DRAFT:
            raise ValidationError({"detail": MSG_STATE})
        entry = PayrollEntry.objects.select_for_update().get(pk=entry.pk)
        if "allowances" in data:
            entry.allowances = money(data["allowances"], MSG_AMOUNT, "allowances")
        if "deductions" in data:
            entry.deductions = money(data["deductions"], MSG_AMOUNT, "deductions")
        if "note" in data:
            note = str(data["note"] or "").strip()
            if len(note) > 300:
                raise ValidationError({"note": MSG_NOTE_LONG})
            entry.note = note
        entry.net = entry.base_salary + entry.allowances - entry.deductions
        if entry.net < 0:
            raise ValidationError({"deductions": MSG_NET})
        entry.save()
        record(actor, run, "entry_updated", to_value=entry.user.full_name)  # who, never how much
    return entry


def approve(actor, run):
    with transaction.atomic():
        run = _locked(run.pk)
        if run.status != Status.DRAFT:
            raise ValidationError({"detail": MSG_STATE})
        if not run.entries.exists():
            raise ValidationError({"detail": MSG_EMPTY})
        run.status, run.approved_by, run.approved_at = Status.APPROVED, actor, timezone.now()
        run.save()
        record(actor, run, "approved", from_value="draft", to_value="ceo_approved")
    head = User.objects.filter(is_active=True, department__name="HR", is_dept_head=True).first()
    notify(head, "payroll_approved", link=f"/payroll/{run.pk}", dedupe_key=f"payroll-approved:{run.pk}:{int(run.approved_at.timestamp())}", ref=run.month.strftime("%Y-%m"))
    return run


def reopen(actor, run, reason):
    reason = str(reason or "").strip()
    if not reason:
        raise ValidationError({"reason": MSG_REASON})
    if len(reason) > 300:
        raise ValidationError({"reason": MSG_NOTE_LONG})
    with transaction.atomic():
        run = _locked(run.pk)
        if run.status != Status.APPROVED:
            raise ValidationError({"detail": MSG_STATE})
        run.status, run.approved_by, run.approved_at = Status.DRAFT, None, None
        run.save()
        record(actor, run, "reopened", from_value="ceo_approved", to_value="draft", comment=reason)
    head = User.objects.filter(is_active=True, department__name="HR", is_dept_head=True).first()
    notify(head, "payroll_reopened", link=f"/payroll/{run.pk}", ref=run.month.strftime("%Y-%m"), name=reason[:120])
    return run


def mark_paid(actor, run):
    with transaction.atomic():
        run = _locked(run.pk)
        if run.status != Status.APPROVED:
            raise ValidationError({"detail": MSG_STATE})
        run.status, run.paid_by, run.paid_at = Status.PAID, actor, timezone.now()
        run.save()
        record(actor, run, "paid", from_value="ceo_approved", to_value="paid")
        people = list(User.objects.filter(payroll_entries__run=run, is_active=True))
    for u in people:
        notify(u, "payslip_ready", link="/payroll", dedupe_key=f"payslip:{run.pk}:{u.pk}", ref=run.month.strftime("%Y-%m"))
    return run
