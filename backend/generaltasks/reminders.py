"""Daily job for general tasks: one overdue alert per deadline. A new deadline starts a new round, so it can alert again."""
from django.utils import timezone

from core.mywork import daily_job
from notifications.service import notify

from .models import GeneralTask


def overdue_alerts(today=None):
    today = today or timezone.localdate()
    sent = 0
    for t in GeneralTask.objects.filter(status="open", deadline__lt=today).select_related("assignee", "assigned_by"):
        key = f"gtaskoverdue:{t.pk}:{t.alert_round}"
        link = f"/tasks?open={t.pk}"
        sent += bool(notify(t.assignee, "gtask_overdue", link=link, dedupe_key=key, ref=t.title[:120], name=t.deadline.isoformat()))
        if t.assigned_by_id != t.assignee_id:
            sent += bool(notify(t.assigned_by, "gtask_overdue_given", link=link, dedupe_key=key, ref=t.title[:120], name=t.assignee.full_name))
    return sent


@daily_job("general_tasks_daily")
def run(today=None):
    return overdue_alerts(today)
