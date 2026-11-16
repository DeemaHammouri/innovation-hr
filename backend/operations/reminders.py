"""Daily Operation jobs: create the recurring tasks that are due, and nudge about overdue tasks and QA meetings. Idempotent."""
from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from clients.models import Client
from core.mywork import daily_job
from notifications.service import notify

from . import services
from .models import QAMeeting, TaskInstance


def overdue_tasks(today=None):
    today = today or timezone.localdate()
    sent = 0
    for t in TaskInstance.objects.filter(status__in=TaskInstance.ACTIVE, due_date__lt=today).select_related("client", "assignee"):
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


def escalate_overdue(today=None):
    """A task that stays overdue is escalated by the system: level 1 (the Operation head) after the first number of days, level 2 (the CEO)
    after the second (settings.TASK_ESCALATION_DAYS). One row per task and level, so repeating the job changes nothing."""
    from django.conf import settings

    from . import lifecycle
    from .models import Escalation

    today = today or timezone.localdate()
    first, second = getattr(settings, "TASK_ESCALATION_DAYS", (2, 5))
    made = 0
    for t in TaskInstance.objects.filter(status__in=TaskInstance.ACTIVE, due_date__lt=today).select_related("client", "assignee"):
        late = (today - t.due_date).days
        have = set(Escalation.objects.filter(task=t).values_list("level", flat=True))
        for level, after in ((1, first), (2, second)):
            if late >= after and level not in have:
                try:
                    lifecycle.escalate(None, t, f"Overdue by {late} days.", auto=True)
                    made += 1
                except ValidationError:  # the task changed under us, or the level was taken a moment ago
                    pass
                break  # one level per run, so the CEO hears about it a day after the head
    return made


@daily_job("operation_daily")
def run(today=None):
    made = services.generate_due(today)
    return made + overdue_tasks(today) + overdue_meetings(today) + services.expire_documents(today) + escalate_overdue(today)
