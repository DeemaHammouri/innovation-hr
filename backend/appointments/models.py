from django.conf import settings
from django.db import models

from core.models import TimeStamped


class Appointment(TimeStamped):
    class Type(models.TextChoices):
        MEETING = "meeting", "Meeting"
        CALL = "call", "Call"
        VISIT = "visit", "Visit"
        FOLLOW_UP = "follow_up", "Follow-up"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    type = models.CharField(max_length=12, choices=Type.choices, default=Type.MEETING, db_index=True)
    title = models.CharField(max_length=200)
    lead = models.ForeignKey("leads.Lead", on_delete=models.PROTECT, related_name="appointments", null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="appointments")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)  # when it was completed or cancelled
    cancel_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["starts_at", "id"]
        indexes = [models.Index(fields=["owner", "status", "starts_at"]), models.Index(fields=["lead", "type", "status"])]
