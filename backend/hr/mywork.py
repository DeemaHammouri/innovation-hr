"""HR items on My Work: leave to decide, payroll to approve or pay. Never any salary figure."""
from core.mywork import provider
from core.roles import CEO, HR_HEAD, role_key

from .models import LeaveRequest, PayrollRun

CAP = 50


@provider
def hr_items(user):
    role = role_key(user)
    out = []
    if role in (HR_HEAD, CEO):
        pending = LeaveRequest.objects.filter(status="pending").exclude(user=user).select_related("user", "leave_type")
        if role == CEO:
            pending = pending.filter(user__department__name="HR", user__is_dept_head=True)
        for r in pending.order_by("start_date")[:CAP]:
            out.append({"kind": "leave_decide", "section": "leave", "ref": r.leave_type.name_en, "title": r.user.full_name, "link": "/leave?tab=requests", "due": r.start_date.isoformat(), "overdue": False})
        status = "draft" if role == CEO else "ceo_approved"
        kind = "payroll_approve" if role == CEO else "payroll_pay"
        for run in PayrollRun.objects.filter(status=status):
            out.append({"kind": kind, "section": "payroll", "ref": run.month.strftime("%Y-%m"), "title": run.month.strftime("%Y-%m"), "link": f"/payroll/{run.pk}", "due": None, "overdue": False})
    return out
