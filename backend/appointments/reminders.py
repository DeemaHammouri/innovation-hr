"""Appointment reminders. Idempotent: the dedupe key holds the start time, so each person hears once per scheduled time, and a
rescheduled appointment reminds again at its new time."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from notifications.service import notify

from .models import Appointment
from .services import link, local_when


def run():
    window = timedelta(minutes=getattr(settings, "APPOINTMENT_REMINDER_MINUTES", 60))
    now = timezone.now()
    sent = 0
    due = Appointment.objects.filter(status="scheduled", starts_at__gt=now, starts_at__lte=now + window).select_related("owner")
    for appt in due:
        key = f"appt-reminder:{appt.pk}:{appt.starts_at.isoformat()}"
        sent += bool(notify(appt.owner, "appointment_reminder", link=link(appt), dedupe_key=key, name=appt.title, when=local_when(appt)))
    return sent
