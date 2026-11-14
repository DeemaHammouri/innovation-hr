from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import TimeStamped


class ChecklistItem(TimeStamped):
    """One KYC / legal document a client must provide. Copied from the CEO's template, then customisable per client."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        UPLOADED = "uploaded", "Uploaded"
        VERIFIED = "verified", "Verified"
        NOT_APPLICABLE = "not_applicable", "Not applicable"

    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="checklist")
    template_item = models.ForeignKey("lookups.ChecklistTemplateItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    name_en = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120)
    required = models.BooleanField(default=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    na_reason = models.TextField(blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    verified_at = models.DateTimeField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.CheckConstraint(condition=~Q(status="not_applicable") | ~Q(na_reason=""), name="checklist_na_needs_reason"),
        ]


class RecurringTask(TimeStamped):
    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        BIWEEKLY = "biweekly", "Every 2 weeks"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"
        CUSTOM = "custom", "Every N days"

    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="recurring_tasks")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    frequency = models.CharField(max_length=10, choices=Frequency.choices)
    interval_days = models.PositiveSmallIntegerField(null=True, blank=True)
    start_date = models.DateField()
    occurrences = models.PositiveIntegerField(default=0)  # how many due dates have been passed so far (created or skipped over)
    next_due = models.DateField(db_index=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["client_id", "title", "id"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(frequency="custom") | (Q(interval_days__gte=1) & Q(interval_days__lte=365)), name="recurring_custom_interval_range",
            ),
        ]


class TaskInstance(TimeStamped):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"
        SKIPPED = "skipped", "Skipped"

    recurring = models.ForeignKey(RecurringTask, on_delete=models.PROTECT, related_name="instances")
    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="tasks")
    title = models.CharField(max_length=150)
    due_date = models.DateField(db_index=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN, db_index=True)
    completion_note = models.TextField(blank=True)
    skip_reason = models.TextField(blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_date", "id"]
        constraints = [
            models.UniqueConstraint(fields=["recurring", "due_date"], name="task_one_instance_per_due_date"),
            models.CheckConstraint(condition=~Q(status="skipped") | ~Q(skip_reason=""), name="task_skip_needs_reason"),
        ]


class QAMeeting(TimeStamped):
    """A follow-up quality-assurance meeting with a client."""

    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="qa_meetings")
    held_on = models.DateField()
    notes = models.TextField()
    next_date = models.DateField(null=True, blank=True)
    logged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-held_on", "-id"]
