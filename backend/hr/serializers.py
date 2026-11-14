from rest_framework import serializers

from . import access
from .models import EmployeeSalary, LeaveRequest, LeaveType, PayrollEntry, PayrollRun


def money(v):
    return f"{v:.2f}"


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ["id", "name_en", "name_ar", "paid", "annual_days", "is_active", "sort_order"]
        read_only_fields = fields


class LeaveRequestSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    department = serializers.CharField(source="user.department.name", read_only=True)
    type_en = serializers.CharField(source="leave_type.name_en", read_only=True)
    type_ar = serializers.CharField(source="leave_type.name_ar", read_only=True)
    paid = serializers.BooleanField(source="leave_type.paid", read_only=True)
    decided_by_name = serializers.CharField(source="decided_by.full_name", default=None, read_only=True)
    can_decide = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = [
            "id", "user", "user_name", "department", "leave_type", "type_en", "type_ar", "paid", "start_date", "end_date", "days", "reason", "status",
            "decided_by_name", "decided_at", "decision_note", "created_at", "can_decide", "can_cancel",
        ]
        read_only_fields = fields

    def get_can_decide(self, r):
        return r.status == "pending" and access.can_decide(self.context["request"].user, r)

    def get_can_cancel(self, r):
        u = self.context["request"].user
        return r.user_id == u.pk and (r.status == "pending" or (r.status == "approved" and r.start_date > self.context["today"]))


class SalarySerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    department = serializers.CharField(source="user.department.name", read_only=True)
    base_salary = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeSalary
        fields = ["id", "user", "user_name", "department", "base_salary", "currency", "updated_at"]
        read_only_fields = fields

    def get_base_salary(self, s):
        return money(s.base_salary)


class EntrySerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    department = serializers.CharField(source="user.department.name", read_only=True)
    base_salary = serializers.SerializerMethodField()
    allowances = serializers.SerializerMethodField()
    deductions = serializers.SerializerMethodField()
    net = serializers.SerializerMethodField()

    class Meta:
        model = PayrollEntry
        fields = ["id", "user", "user_name", "department", "base_salary", "allowances", "deductions", "net", "note"]
        read_only_fields = fields

    def get_base_salary(self, e):
        return money(e.base_salary)

    def get_allowances(self, e):
        return money(e.allowances)

    def get_deductions(self, e):
        return money(e.deductions)

    def get_net(self, e):
        return money(e.net)


class RunSerializer(serializers.ModelSerializer):
    approved_by_name = serializers.CharField(source="approved_by.full_name", default=None, read_only=True)
    paid_by_name = serializers.CharField(source="paid_by.full_name", default=None, read_only=True)
    month = serializers.SerializerMethodField()
    people = serializers.IntegerField(read_only=True, default=0)
    total_net = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = PayrollRun
        fields = ["id", "month", "currency", "status", "approved_by_name", "approved_at", "paid_by_name", "paid_at", "people", "total_net", "permissions", "created_at"]
        read_only_fields = fields

    def get_month(self, r):
        return r.month.strftime("%Y-%m")

    def get_total_net(self, r):
        return money(getattr(r, "net_total", None) or 0)

    def get_permissions(self, r):
        u = self.context["request"].user
        return {
            "can_edit": access.manages_payroll(u) and r.status == "draft",
            "can_approve": access.is_ceo(u) and r.status == "draft",
            "can_reopen": access.is_ceo(u) and r.status == "ceo_approved",
            "can_pay": access.manages_payroll(u) and r.status == "ceo_approved",
        }


class PayslipSerializer(serializers.ModelSerializer):
    month = serializers.SerializerMethodField()
    currency = serializers.CharField(source="run.currency", read_only=True)
    paid_at = serializers.DateTimeField(source="run.paid_at", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    department = serializers.CharField(source="user.department.name", read_only=True)
    base_salary = serializers.SerializerMethodField()
    allowances = serializers.SerializerMethodField()
    deductions = serializers.SerializerMethodField()
    net = serializers.SerializerMethodField()

    class Meta:
        model = PayrollEntry
        fields = ["id", "month", "currency", "paid_at", "user_name", "department", "base_salary", "allowances", "deductions", "net", "note"]
        read_only_fields = fields

    def get_month(self, e):
        return e.run.month.strftime("%Y-%m")

    def get_base_salary(self, e):
        return money(e.base_salary)

    def get_allowances(self, e):
        return money(e.allowances)

    def get_deductions(self, e):
        return money(e.deductions)

    def get_net(self, e):
        return money(e.net)
