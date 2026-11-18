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
        QUARTERLY = "quarterly", "Every 3 months"
        SEMIANNUAL = "semiannual", "Every 6 months"
        YEARLY = "yearly", "Yearly"
        CUSTOM = "custom", "Every N days"
        WORKDAYS = "workdays", "Every working day"

    class DayRule(models.TextChoices):  # monthly, quarterly, semi-annual and yearly rules only
        DATE = "date", "Same day of the month as the start date"
        FIRST_WORKDAY = "first_workday", "First working day of the month"
        LAST_WORKDAY = "last_workday", "Last working day of the month"
        NTH_WEEKDAY = "nth_weekday", "A weekday of the month (2nd Tuesday, last Thursday)"

    class WeekendPolicy(models.TextChoices):  # what to do when the date is a weekend day or a public holiday
        NEXT = "next", "Move to the next working day"
        PREVIOUS = "previous", "Move to the previous working day"
        KEEP = "keep", "Keep the date"
        SKIP = "skip", "Skip that time"

    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="recurring_tasks")
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    frequency = models.CharField(max_length=10, choices=Frequency.choices)
    version = models.PositiveIntegerField(default=1)  # a new schedule starts a new version; tasks already made keep theirs
    interval_days = models.PositiveSmallIntegerField(null=True, blank=True)
    day_rule = models.CharField(max_length=14, choices=DayRule.choices, default=DayRule.DATE)
    nth = models.SmallIntegerField(null=True, blank=True)  # nth_weekday only: 1 to 4, or -1 for the last
    weekday = models.SmallIntegerField(null=True, blank=True)  # nth_weekday only: 0 Monday to 6 Sunday
    weekend_policy = models.CharField(max_length=8, choices=WeekendPolicy.choices, default=WeekendPolicy.NEXT)
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
            # A day rule other than "date" only makes sense for the frequencies that step by months.
            models.CheckConstraint(
                condition=Q(day_rule="date") | Q(frequency__in=["monthly", "quarterly", "semiannual", "yearly"]), name="recurring_day_rule_needs_months",
            ),
            models.CheckConstraint(
                condition=~Q(day_rule="nth_weekday") | (Q(nth__isnull=False, nth__in=[1, 2, 3, 4, -1]) & Q(weekday__isnull=False, weekday__gte=0, weekday__lte=6)), name="recurring_nth_weekday_complete",  # isnull=False: NULL would pass a CHECK
            ),
        ]


class TaskInstance(TimeStamped):
    class Status(models.TextChoices):
        OPEN = "open", "Open"  # created, nobody has started
        IN_PROGRESS = "in_progress", "In progress"
        WAITING = "waiting", "Waiting"  # for the client or someone else, with a reason
        BLOCKED = "blocked", "Blocked"  # something stops the work, with a reason
        SUBMITTED = "submitted", "Submitted"  # the assignee says it is finished; the manager decides
        DONE = "done", "Done"
        SKIPPED = "skipped", "Skipped"

    ACTIVE = ("open", "in_progress", "waiting", "blocked")  # still on someone's plate (and can become overdue)

    recurring = models.ForeignKey(RecurringTask, on_delete=models.PROTECT, related_name="instances")
    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="tasks")
    title = models.CharField(max_length=150)
    due_date = models.DateField(db_index=True)
    rule_version = models.PositiveIntegerField(default=1)
    period = models.DateField()  # the stretch of time this task covers (see operations/recurrence.py)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True)
    progress = models.PositiveSmallIntegerField(default=0)  # 0 to 100, set by the assignee
    started_at = models.DateTimeField(null=True, blank=True)
    status_reason = models.TextField(blank=True)  # why it is waiting or blocked
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)  # the manager's note when sending it back
    completion_note = models.TextField(blank=True)
    skip_reason = models.TextField(blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    closed_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.period is None:  # a task made by hand (or by an older caller) is its own period
            from .recurrence import period

            self.period = period(self.recurring.frequency, self.due_date)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["due_date", "id"]
        constraints = [
            models.UniqueConstraint(fields=["recurring", "rule_version", "period"], name="task_one_instance_per_rule_version_period"),
            models.CheckConstraint(condition=~Q(status="skipped") | ~Q(skip_reason=""), name="task_skip_needs_reason"),
            models.CheckConstraint(condition=Q(progress__lte=100), name="task_progress_at_most_100"),
            models.CheckConstraint(condition=~Q(status__in=["waiting", "blocked"]) | ~Q(status_reason=""), name="task_wait_or_block_needs_reason"),
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


class Escalation(models.Model):
    """A task that needs someone above the assignee. Level 1 goes to the Operation head, level 2 to the CEO. One row per task and
    level, enforced by the database, so a task is never escalated to the same level twice however many times the job runs."""

    class Level(models.IntegerChoices):
        HEAD = 1, "Operation head"
        CEO = 2, "CEO"

    task = models.ForeignKey(TaskInstance, on_delete=models.CASCADE, related_name="escalations")
    level = models.PositiveSmallIntegerField(choices=Level.choices)
    reason = models.TextField(blank=True)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")  # empty: raised by the system (overdue)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["task_id", "level"]
        constraints = [
            models.UniqueConstraint(fields=["task", "level"], name="escalation_one_per_task_and_level"),
            models.CheckConstraint(condition=Q(level__in=[1, 2]), name="escalation_level_is_1_or_2"),
        ]


class Deliverable(models.Model):
    """A finished piece of work (a report, a filing) the client may see. Operation attaches the file to the task and publishes it;
    the client's portal lists it and the client acknowledges receipt. Nothing here carries prices."""

    task = models.ForeignKey(TaskInstance, on_delete=models.PROTECT, related_name="deliverables")
    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="deliverables")
    attachment = models.ForeignKey("files.Attachment", on_delete=models.PROTECT, related_name="+")
    title = models.CharField(max_length=150)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    published_at = models.DateTimeField(auto_now_add=True)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["attachment"], name="deliverable_published_once")]
