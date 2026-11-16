"""What Operation puts on a person's My Work list."""
from django.utils import timezone

from core.mywork import provider

from .models import ChecklistItem, TaskInstance

CAP = 50


@provider
def operation_items(user):
    if not user.has_capability("operation.work"):
        return []
    manager = user.has_capability("operation.manage")
    today = timezone.localdate()
    out = []
    tasks = TaskInstance.objects.filter(status="open", due_date__lte=today).select_related("client").order_by("due_date")
    tasks = tasks.filter(assignee__in=[user, None]) | tasks.filter(assignee__isnull=True) if manager else tasks.filter(assignee=user)
    for t in tasks.distinct()[:CAP]:
        out.append({"kind": "op_task", "section": "operation", "ref": t.title, "title": t.client.company_name, "link": "/operation?tab=tasks", "due": t.due_date.isoformat(), "overdue": t.due_date < today})
    for i in ChecklistItem.objects.filter(status="uploaded", archived_at__isnull=True).select_related("client").order_by("updated_at")[:CAP]:
        out.append({"kind": "op_verify", "section": "operation", "ref": i.name_en, "title": i.client.company_name, "link": f"/operation/{i.client_id}", "due": None, "overdue": False})
    return out


@provider
def handover_items(user):
    """Commercial: handovers to fill in or fix. The Operation head and the CEO: handovers waiting for a decision."""
    from .models import Handover

    out = []
    if user.has_capability("handover.write"):
        mine = Handover.objects.filter(status__in=["draft", "returned"])
        if not user.has_capability("lead.manage"):
            mine = mine.filter(prepared_by=user)
        out += [
            {"kind": "handover_fill", "section": "handovers", "ref": h.ref, "title": h.client.company_name, "link": f"/handovers/{h.pk}", "due": None, "overdue": False}
            for h in mine.select_related("client").order_by("created_at")[:CAP]
        ]
    if user.has_capability("handover.decide"):
        waiting = Handover.objects.filter(status__in=["submitted", "escalated"]).select_related("client").order_by("submitted_at")
        out += [
            {"kind": "handover_decide", "section": "handovers", "ref": h.ref, "title": h.client.company_name, "link": f"/handovers/{h.pk}", "due": None, "overdue": False}
            for h in waiting[:CAP]
        ]
    return out
