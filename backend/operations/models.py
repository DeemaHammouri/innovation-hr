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
        EXPIRED = "expired", "Expired"
        NOT_APPLICABLE = "not_applicable", "Not applicable"

    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="checklist")
    template_item = models.ForeignKey("lookups.ChecklistTemplateItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    name_en = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120)
    required = models.BooleanField(default=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    na_reason = models.TextField(blank=True)
    expires_required = models.BooleanField(default=False)  # a verification must carry the date the document stops being valid
    expires_on = models.DateField(null=True, blank=True, db_index=True)
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


class Handover(TimeStamped):
    """What Commercial tells Operation about a client whose contract is signed. It carries no prices, no payment terms and no contract file:
    only what Operation needs to start work (services, scope, contacts, start date).

    draft -> submitted (Commercial) -> accepted (Operation head: a Project is created)
                                    -> returned (with a comment; Commercial edits and submits again)
                                    -> escalated (Operation head to the CEO, with a reason; the CEO then accepts or returns)"""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Waiting for Operation"
        RETURNED = "returned", "Returned to Commercial"
        ESCALATED = "escalated", "Escalated to the CEO"
        ACCEPTED = "accepted", "Accepted"

    ref = models.CharField(max_length=20, unique=True)
    contract = models.OneToOneField("contracts.Contract", on_delete=models.PROTECT, related_name="handover")
    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="handovers")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    services = models.TextField(blank=True)
    scope_notes = models.TextField(blank=True)
    contacts = models.TextField(blank=True)
    special_requirements = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_comment = models.TextField(blank=True)
    escalated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "created_at"], name="handover_status_idx")]


class Project(TimeStamped):
    """The work for one client, created the moment Operation accepts a handover (never before, never twice)."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ON_HOLD = "on_hold", "On hold"
        CLOSED = "closed", "Closed"

    ref = models.CharField(max_length=20, unique=True)
    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="projects")
    handover = models.OneToOneField(Handover, on_delete=models.PROTECT, related_name="project")
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    start_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]


class ChecklistItemVersion(models.Model):
    """Every document ever filed against a checklist item, in order. The newest one is what Operation verifies; older ones stay as history.

    Replacing a verified document does not edit the old record: it adds version N+1 (uploaded, not verified), marks the earlier ones
    superseded, and sends the item back to Uploaded, so a client is never "verified" on a document nobody has checked."""

    class State(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        VERIFIED = "verified", "Verified"
        SUPERSEDED = "superseded", "Superseded"

    item = models.ForeignKey(ChecklistItem, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    attachment = models.ForeignKey("files.Attachment", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    filename = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=12, choices=State.choices, default=State.UPLOADED)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-number"]
        constraints = [models.UniqueConstraint(fields=["item", "number"], name="kyc_one_version_number_per_item")]


class ProjectStaff(models.Model):
    """Who works on a project. Exactly one active primary employee (the database enforces it) plus any number of support people.
    Nothing is deleted: a person who leaves a project gets an end date and the reason."""

    class Role(models.TextChoices):
        PRIMARY = "primary", "Primary"
        SUPPORT = "support", "Support"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="staff")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    role = models.CharField(max_length=8, choices=Role.choices)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    assigned_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ended_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    end_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["role", "assigned_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["project"], condition=Q(role="primary", ended_at__isnull=True), name="project_one_active_primary"),
            models.UniqueConstraint(fields=["project", "user"], condition=Q(ended_at__isnull=True), name="project_person_once_while_active"),
            models.CheckConstraint(condition=Q(ended_at__isnull=True) | ~Q(end_reason=""), name="project_staff_end_needs_reason"),
        ]
