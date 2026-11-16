"""What general tasks put on a person's My Work list: their own open tasks that are due today or late."""
from django.utils import timezone

from core.mywork import provider

from .models import GeneralTask

CAP = 50


@provider
def general_task_items(user):
    if not user.has_capability("gtask.access"):
        return []
    today = timezone.localdate()
    rows = GeneralTask.objects.filter(assignee=user, status="open", deadline__lte=today).select_related("assigned_by").order_by("deadline")[:CAP]
    return [
        {"kind": "gtask", "section": "tasks", "ref": t.title, "title": t.assigned_by.full_name, "link": f"/tasks?open={t.pk}", "due": t.deadline.isoformat(), "overdue": t.deadline < today}
        for t in rows
    ]
