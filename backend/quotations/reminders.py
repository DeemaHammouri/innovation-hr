"""Overdue quotation follow-ups. Idempotent: each person hears about each overdue date once."""
from django.utils import timezone

from core.mywork import daily_job
from notifications.service import notify

from .models import Quotation
from .services import commercial_head


@daily_job("quotation_reminders")
def run():
    today = timezone.localdate()
    head = commercial_head()
    sent = 0
    for q in Quotation.objects.filter(status="waiting", next_follow_up__lt=today).select_related("lead", "lead__assigned_to"):
        who = q.lead.assigned_to if q.lead.assigned_to_id and q.lead.assigned_to.is_active else head
        sent += bool(notify(who, "followup_overdue", link=f"/quotations/{q.pk}", dedupe_key=f"qfollowup:{q.pk}:{q.next_follow_up}", ref=q.ref, name=q.lead.company_name))
    return sent
