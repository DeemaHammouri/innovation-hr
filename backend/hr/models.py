"""
HR: leave, salaries and payroll. Attendance has no tables of its own: it is derived from the sign-in / sign-out log.

Salary data lives only in EmployeeSalary and PayrollEntry. Nothing else (history, notifications, logs, search, user
payloads) ever receives a salary figure.
"""
from django.conf import settings
from django.db import models

from core.models import TimeStamped


class LeaveType(models.Model):
    name_en = models.CharField(max_length=80)
    name_ar = models.CharField(max_length=80)
    paid = models.BooleanField(default=True)
    annual_days = models.PositiveSmallIntegerField(null=True, blank=True)  # allowance per calendar year; empty = no cap
    is_active = models.BooleanField(default=True, db_index=True)  # switched off, never deleted
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name_en


class LeaveRequest(TimeStamped):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="leave_requests")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="requests")
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.PositiveSmallIntegerField()  # working days, counted when the request is made
    reason = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-start_date", "-id"]
        indexes = [models.Index(fields=["user", "start_date"]), models.Index(fields=["status", "start_date"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(end_date__gte=models.F("start_date")), name="leave_dates_in_order"),
            models.CheckConstraint(condition=models.Q(days__gt=0), name="leave_days_positive"),
            models.CheckConstraint(condition=~models.Q(status="rejected") | ~models.Q(decision_note=""), name="leave_rejection_needs_note"),
        ]


class EmployeeSalary(TimeStamped):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="salary")
    base_salary = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="JOD")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(base_salary__gte=0), name="salary_not_negative")]


class PayrollRun(TimeStamped):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "ceo_approved", "CEO approved"
        PAID = "paid", "Paid"

    month = models.DateField(unique=True)  # always the first day of the month
    currency = models.CharField(max_length=3, default="JOD")
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.DRAFT, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-month"]
        constraints = [
            models.CheckConstraint(condition=models.Q(month__day=1), name="payroll_month_is_first_day"),
            models.CheckConstraint(
                condition=~models.Q(status="ceo_approved") | models.Q(approved_by__isnull=False), name="payroll_approved_has_approver"
            ),
            models.CheckConstraint(condition=~models.Q(status="paid") | models.Q(paid_by__isnull=False), name="payroll_paid_has_payer"),
        ]


class PayrollEntry(TimeStamped):
    run = models.ForeignKey(PayrollRun, on_delete=models.PROTECT, related_name="entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payroll_entries")
    base_salary = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["user__full_name", "id"]
        constraints = [
            models.UniqueConstraint(fields=["run", "user"], name="payroll_one_entry_per_person_per_run"),
            models.CheckConstraint(condition=models.Q(allowances__gte=0) & models.Q(deductions__gte=0), name="payroll_adjustments_not_negative"),
            models.CheckConstraint(condition=models.Q(net__gte=0), name="payroll_net_not_negative"),
            models.CheckConstraint(
                condition=models.Q(net=models.F("base_salary") + models.F("allowances") - models.F("deductions")), name="payroll_net_adds_up"
            ),
        ]
