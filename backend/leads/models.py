import re

from django.conf import settings
from django.db import models

from core.fields import UpdatedAtField
from core.models import Archivable, TimeStamped

from .normalize import normalize_email, normalize_phone


def phone_key(raw):
    """The phone as E.164. 0797707154, 962797707154 and +962 79 770 7154 are all the same key."""
    return normalize_phone(raw)


def email_key(raw):
    return normalize_email(raw)


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
    skip_report = models.JSONField(default=list, blank=True)  # one entry per row that did not come in, with its reasons
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
    contact_name = models.CharField(max_length=150, blank=True)  # the contact person's name
    position = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    source = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    phone_key = models.CharField(max_length=20, blank=True, db_index=True)  # E.164; unique among open leads
    email_key = models.CharField(max_length=254, blank=True, db_index=True)  # lower-case; unique among open leads

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
        constraints = [
            # Archived leads are out of the way (an undone import can be imported again), so they do not hold a number or an email.
            models.UniqueConstraint(fields=["phone_key"], condition=models.Q(archived_at__isnull=True) & ~models.Q(phone_key=""), name="uniq_open_lead_phone"),
            models.UniqueConstraint(fields=["email_key"], condition=models.Q(archived_at__isnull=True) & ~models.Q(email_key=""), name="uniq_open_lead_email"),
        ]
        indexes = [models.Index(fields=["created_at"], name="lead_created_idx"), models.Index(fields=["status", "next_follow_up"]), models.Index(fields=["assigned_to", "status"])]

    def __str__(self):
        return f"{self.ref} {self.company_name}"

    def save(self, *args, **kwargs):
        self.phone_key = phone_key(self.phone)
        self.email_key = email_key(self.email)
        if self.phone_key:
            self.phone = self.phone_key  # stored as typed-then-normalised: always +<country><number>
        self.email = self.email_key
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


class LeadStatusChange(models.Model):
    """Every move of a lead between statuses: who, from, to, when. Written in the same transaction as the move, never edited."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="status_changes")
    from_status = models.CharField(max_length=12, blank=True)  # blank for the first entry (the lead was created)
    to_status = models.CharField(max_length=12)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    changed_at = models.DateTimeField(db_index=True)
    follow_up_date = models.DateField(null=True, blank=True)  # when the move was to Waiting
    rejection_reason = models.ForeignKey("lookups.RejectionReason", on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["changed_at", "id"]
        indexes = [models.Index(fields=["lead", "changed_at"])]


class LeadTarget(models.Model):
    """A number of leads a Marketing employee is asked to add from one date to another (both included, company time zone).
    `user` empty means the whole Marketing team (used for targets converted from the old monthly company target)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lead_targets", null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    target = models.PositiveIntegerField()
    set_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = UpdatedAtField()

    class Meta:
        ordering = ["start_date", "id"]
        constraints = [models.CheckConstraint(condition=models.Q(end_date__gte=models.F("start_date")), name="target_end_after_start")]
        indexes = [models.Index(fields=["user", "start_date", "end_date"])]
