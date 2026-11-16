"""What leads put on a person's My Work list."""
from django.utils import timezone

from core.mywork import provider

from .models import Lead
from .sla import first_contact_overdue, sla_now

CAP = 50


def item(kind, lead, due=None, overdue=False):
    return {
        "kind": kind, "section": "pipeline", "ref": lead.ref, "title": lead.company_name,
        "link": f"/leads/{lead.pk}", "due": due.isoformat() if due else None, "overdue": overdue,
    }


@provider
def lead_items(user):
    head = user.has_capability("lead.manage")
    if not (head or user.has_capability("lead.work_assigned")):
        return []
    today, now, sla = sla_now()
    open_leads = Lead.objects.filter(archived_at__isnull=True)
    out = []
    if head:
        for lead in open_leads.filter(status="new", assigned_to__isnull=True).order_by("created_at")[:CAP]:
            out.append(item("lead_assign", lead, overdue=first_contact_overdue(lead, now, sla)))
    mine = open_leads.filter(assigned_to=user)
    for lead in mine.filter(status="new").order_by("assigned_at")[:CAP]:
        out.append(item("lead_contact", lead, overdue=first_contact_overdue(lead, now, sla)))
    for lead in mine.filter(status="contacted").order_by("last_contacted_at")[:CAP]:
        out.append(item("lead_outcome", lead))
    for lead in mine.filter(status="waiting", next_follow_up__lte=today).order_by("next_follow_up")[:CAP]:
        late = lead.next_follow_up < today
        out.append(item("followup_overdue" if late else "followup_due", lead, due=lead.next_follow_up, overdue=late))
    return out
