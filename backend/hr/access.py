"""
Who can see what in HR.

* Attendance: everyone sees their own; HR (head and members) and the CEO see everyone's.
* Leave: everyone except the CEO requests; the HR head decides (the CEO decides the HR head's); HR and the CEO see all requests;
  the calendar shows approved leave to HR and the CEO (everyone), to a department head (their department) and to others (themselves).
* Salaries and payroll: the HR head and the CEO only, plus each employee's own payslip once the run is paid.
"""
from accounts.models import User
from core.roles import CEO, HR_HEAD, HR_MEMBER, role_key


def is_ceo(user):
    return role_key(user) == CEO


def is_hr_head(user):
    return role_key(user) == HR_HEAD


def is_hr(user):
    return role_key(user) in (HR_HEAD, HR_MEMBER)


def sees_everyone(user):
    return role_key(user) in (CEO, HR_HEAD, HR_MEMBER)


def can_request_leave(user):
    return role_key(user) is not None and not is_ceo(user)


def can_decide(user, request):
    """The HR head decides everyone's leave except their own; the CEO decides the HR head's."""
    if request.user_id == user.pk:
        return False
    if request.user.department.name == "HR" and request.user.is_dept_head:
        return is_ceo(user)
    return is_hr_head(user)


def sees_payroll(user):
    return role_key(user) in (CEO, HR_HEAD)


def manages_payroll(user):
    return is_hr_head(user)
