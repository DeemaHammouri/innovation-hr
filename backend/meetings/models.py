from django.conf import settings
from django.db import models

from core.models import TimeStamped
from files.models import private_storage, stored_name


class MeetingReport(TimeStamped):
    """What happened in one completed meeting. One report per appointment.

    draft -> (Commercial head signs) signed -> (CEO approves) approved
                  ^                          |
                  +---- returned (CEO sends it back with a comment; the author edits and the head signs again)"""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SIGNED = "signed", "Signed by Commercial"
        APPROVED = "approved", "Approved by the CEO"
        RETURNED = "returned", "Returned by the CEO"

    appointment = models.OneToOneField("appointments.Appointment", on_delete=models.PROTECT, related_name="report")
    lead = models.ForeignKey("leads.Lead", on_delete=models.PROTECT, related_name="meeting_reports")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    held_on = models.DateField()
    attendees = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    decisions = models.TextField(blank=True)
    next_steps = models.TextField(blank=True)
    signed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    signature = models.FileField(storage=private_storage, upload_to=stored_name, max_length=255, blank=True)
    stamp = models.FileField(storage=private_storage, upload_to=stored_name, max_length=255, blank=True)
    ceo_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    ceo_at = models.DateTimeField(null=True, blank=True)
    ceo_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-held_on", "-id"]
        indexes = [models.Index(fields=["status", "created_at"], name="meetingreport_status_idx")]

    def __str__(self):
        return f"Report {self.appointment_id}"
