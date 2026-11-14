"""Overdue reminders. Idempotent: a dedupe key means each person hears about each overdue item once."""
from core.mywork import daily_job
from notifications.service import notify

from .models import Lead
from .services import commercial_head
from .sla import first_contact_overdue, sla_now


@daily_job("lead_reminders")
def run():
    today, now, sla = sla_now()
    head = commercial_head()
    open_leads = Lead.objects.filter(archived_at__isnull=True).select_related("assigned_to")
    sent = 0
    for lead in open_leads.filter(status="waiting", next_follow_up__lt=today, assigned_to__isnull=False):
        sent += bool(notify(lead.assigned_to, "followup_overdue", link=f"/leads/{lead.pk}", dedupe_key=f"followup:{lead.pk}:{lead.next_follow_up}", ref=lead.ref, name=lead.company_name))
    for lead in open_leads.filter(status="new"):
        if not first_contact_overdue(lead, now, sla):
            continue
        if lead.assigned_to_id:
            sent += bool(notify(lead.assigned_to, "first_contact_overdue", link=f"/leads/{lead.pk}", dedupe_key=f"firstcontact:{lead.pk}", ref=lead.ref, name=lead.company_name))
        elif head:
            sent += bool(notify(head, "assign_needed", link=f"/leads/{lead.pk}", dedupe_key=f"assign:{lead.pk}", ref=lead.ref, name=lead.company_name))
    return sent
