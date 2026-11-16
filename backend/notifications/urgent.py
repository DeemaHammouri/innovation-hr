"""Urgent alerts: work that has sat too long. Run by process_notifications, safe to run as often as you like.

Each alert goes out once per case: its dedupe key holds what started the clock (the assignment, the submission, the appointment's
time), so it is not repeated on the next run, and a new assignment or a rescheduled appointment is a new case.
The waiting times are settings (URGENT_*_MINUTES)."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from audit.models import AuditEntry
from core.access import content_type_for

from .service import notify


def minutes(name, default=60):
    return int(getattr(settings, name, default))


def quotation_assignments():
    """(quotation, when it was handed to its HR person) for quotations still waiting for that person to submit."""
    from quotations.models import Quotation

    out = []
    qs = Quotation.objects.filter(assigned_to__isnull=False, status__in=("requested", "in_preparation", "changes_requested")).select_related("assigned_to", "lead")
    ct = content_type_for(Quotation)
    for q in qs:
        entry = AuditEntry.objects.filter(content_type=ct, object_id=q.pk, action="assigned").order_by("-created_at", "-id").first()
        if entry:
            out.append((q, entry.created_at))
    return out


def hr_alerts(now):
    limit, sent = timedelta(minutes=minutes("URGENT_HR_MINUTES")), 0
    for q, since in quotation_assignments():
        if now - since >= limit:
            sent += bool(notify(q.assigned_to, "urgent_hr", link=f"/quotations/{q.pk}", dedupe_key=f"urgent-hr:{q.pk}:{since.isoformat()}", ref=q.ref, name=q.lead.company_name, minutes=minutes("URGENT_HR_MINUTES")))
    return sent


def commercial_alerts(now):
    from accounts.models import User
    from quotations.models import Quotation

    head = User.objects.filter(is_active=True, department__name="Commercial", is_dept_head=True).first()
    limit, sent = timedelta(minutes=minutes("URGENT_COMMERCIAL_MINUTES")), 0
    for q in Quotation.objects.filter(status="in_review").select_related("lead").prefetch_related("versions"):
        v = max(q.versions.all(), key=lambda v: v.number, default=None)
        if v and v.submitted_at and now - v.submitted_at >= limit:
            sent += bool(notify(head, "urgent_commercial", link=f"/quotations/{q.pk}", dedupe_key=f"urgent-commercial:{q.pk}:{v.submitted_at.isoformat()}", ref=q.ref, name=q.lead.company_name, minutes=minutes("URGENT_COMMERCIAL_MINUTES")))
    return sent


def appointment_alerts(now):
    from appointments.models import Appointment
    from appointments.services import link, local_when

    limit, sent = timedelta(minutes=minutes("URGENT_APPOINTMENT_MINUTES")), 0
    for a in Appointment.objects.filter(status="scheduled", starts_at__lte=now - limit).select_related("owner"):
        sent += bool(notify(a.owner, "urgent_appointment", link=link(a), dedupe_key=f"urgent-appt:{a.pk}:{a.starts_at.isoformat()}", name=a.title, when=local_when(a)))
    return sent


def run():
    now = timezone.now()
    return hr_alerts(now) + commercial_alerts(now) + appointment_alerts(now)
