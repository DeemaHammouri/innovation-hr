"""
Who can see what in HR.

* Attendance: everyone sees their own; HR (head and members) and the CEO see everyone's.
* Leave: everyone except the CEO requests; the HR head decides (the CEO decides the HR head's); HR and the CEO see all requests;
  the calendar shows approved leave to HR and the CEO (everyone), to a department head (their department) and to others (themselves).
* Salaries and payroll: the HR head and the CEO only, plus each employee's own payslip once the run is paid.
"""
from accounts.models import User


def approves_payroll(user):
    """Approves payroll runs (the CEO)."""
    return user.has_capability("hr.payroll_approve")


def decides_hr_head_leave(user):
    return user.has_capability("hr.leave_decide_hr_head")


def is_hr_head(user):
    return user.has_capability("hr.manage")


def is_hr(user):
    return user.has_capability("hr.staff")


def sees_everyone(user):
    return user.has_capability("hr.attendance_all")


def can_request_leave(user):
    return user.has_capability("hr.leave_request")


def can_decide(user, request):
    """The HR head decides everyone's leave except their own; the CEO decides the HR head's."""
    if request.user_id == user.pk:
        return False
    if request.user.department.name == "HR" and request.user.is_dept_head:
        return decides_hr_head_leave(user)
    return is_hr_head(user)


def sees_payroll(user):
    return user.has_capability("hr.payroll_view")


def manages_payroll(user):
    return is_hr_head(user)
