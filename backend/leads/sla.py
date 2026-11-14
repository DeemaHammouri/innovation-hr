from datetime import timedelta

from django.utils import timezone

from lookups.models import SlaSetting


def sla_now():
    """(today in the business time zone, now, SLA settings). Read once per request, not once per lead."""
    return timezone.localdate(), timezone.now(), SlaSetting.get()


def follow_up_overdue(lead, today):
    return lead.status == "waiting" and lead.next_follow_up is not None and lead.next_follow_up < today


def first_contact_overdue(lead, now, sla):
    """A new lead waiting too long for its first contact. The clock starts when it was assigned (or created, if nobody has it yet)."""
    if lead.status != "new" or lead.archived_at:
        return False
    started = lead.assigned_at or lead.created_at
    return now > started + timedelta(hours=sla.first_contact_hours)
