"""Daily Operation jobs: create the recurring tasks that are due, and nudge about overdue tasks and QA meetings. Idempotent."""
from datetime import timedelta

from django.utils import timezone

from clients.models import Client
from core.mywork import daily_job
from notifications.service import notify

from . import services
from .models import QAMeeting, TaskInstance


def overdue_tasks(today=None):
    today = today or timezone.localdate()
    sent = 0
    for t in TaskInstance.objects.filter(status="open", due_date__lt=today).select_related("client", "assignee"):
        who = t.assignee if t.assignee_id and t.assignee.is_active else services.operation_head()
        if who:
            sent += bool(notify(who, "overdue", link="/operation?tab=tasks", dedupe_key=f"taskoverdue:{t.pk}:{t.due_date}", ref=t.title, name=t.client.company_name))
    return sent


def overdue_meetings(today=None):
    today = today or timezone.localdate()
    head = services.operation_head()
    sent = 0
    if not head:
        return 0
    for c in Client.objects.filter(status="active"):
        last = QAMeeting.objects.filter(client=c).order_by("-held_on", "-id").first()
        due = last.next_date if last and last.next_date else (last.held_on if last else (c.activated_at or c.created_at).date()) + timedelta(days=c.qa_cadence_days)
        if due < today:
            sent += bool(notify(head, "qa_overdue", link=f"/operation/{c.pk}", dedupe_key=f"qa:{c.pk}:{due}", ref=c.company_name, name=""))
    return sent


@daily_job("operation_daily")
def run(today=None):
    made = services.generate_due(today)
    return made + overdue_tasks(today) + overdue_meetings(today) + services.expire_documents(today)
