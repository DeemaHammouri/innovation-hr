import re

from django.conf import settings
from django.db import models

from core.models import Archivable, TimeStamped


def phone_key(raw):
    """Digits only, compared by their last 9 digits so +962 79 123 4567 and 0791234567 match. Too-short numbers never match."""
    digits = re.sub(r"\D", "", raw or "")
    return digits[-9:] if len(digits) >= 7 else ""


def email_key(raw):
    return (raw or "").strip().lower()


class ImportBatch(TimeStamped):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        UNDONE = "undone", "Undone"

    ref = models.CharField(max_length=12, unique=True)
    filename = models.CharField(max_length=200)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="import_batches")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    total_rows = models.PositiveIntegerField(default=0)
    imported_count = models.PositiveIntegerField(default=0)
    skipped_errors = models.PositiveIntegerField(default=0)
    skipped_duplicates = models.PositiveIntegerField(default=0)
    undone_at = models.DateTimeField(null=True, blank=True)
    undone_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class Lead(TimeStamped, Archivable):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        WAITING = "waiting", "Waiting"
        QUALIFIED = "qualified", "Qualified"
        REJECTED = "rejected", "Rejected"

    ref = models.CharField(max_length=12, unique=True)
    company_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    source = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    phone_key = models.CharField(max_length=20, blank=True, db_index=True)
    email_key = models.CharField(max_length=254, blank=True, db_index=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="leads_assigned", null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="leads", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="leads_created")

    next_follow_up = models.DateField(null=True, blank=True, db_index=True)
    rejection_reason = models.ForeignKey("lookups.RejectionReason", on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    rejection_note = models.TextField(blank=True)
    first_contacted_at = models.DateTimeField(null=True, blank=True)
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    qualified_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    skipped_quotation_at = models.DateTimeField(null=True, blank=True)
    skipped_quotation_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    archive_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["created_at"], name="lead_created_idx"), models.Index(fields=["status", "next_follow_up"]), models.Index(fields=["assigned_to", "status"])]

    def __str__(self):
        return f"{self.ref} {self.company_name}"

    def save(self, *args, **kwargs):
        self.phone_key = phone_key(self.phone)
        self.email_key = email_key(self.email)
        super().save(*args, **kwargs)


class Interaction(models.Model):
    class Type(models.TextChoices):
        CALL = "call", "Call"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email"
        MEETING = "meeting", "Meeting"
        OTHER = "other", "Other"

    class Outcome(models.TextChoices):
        NONE = "", "No outcome yet"
        WAITING = "waiting", "Waiting"
        REJECTED = "rejected", "Rejected"
        ACCEPTED = "accepted", "Initial acceptance"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="interactions")
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.CALL)
    occurred_at = models.DateTimeField(db_index=True)
    notes = models.TextField(blank=True)
    outcome = models.CharField(max_length=10, choices=Outcome.choices, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
