from django.conf import settings
from django.db import models
from django.db.models import Q


class GeneralTask(models.Model):
    """A task one person gives another, outside any client: the CEO to anyone, a department head to their own department."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="general_tasks")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="general_tasks_given")
    deadline = models.DateField(db_index=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN, db_index=True)
    done_at = models.DateTimeField(null=True, blank=True)
    done_late = models.BooleanField(default=False)  # fixed the moment it is marked done, so a later deadline edit cannot rewrite history
    alert_round = models.PositiveIntegerField(default=0)  # +1 on every deadline change: the overdue alert is one per round, so a new deadline re-arms it
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["deadline", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(status="open", done_at__isnull=True, done_late=False) | Q(status="done", done_at__isnull=False), name="gtask_done_has_a_time"),
            models.CheckConstraint(condition=~Q(title=""), name="gtask_title_not_blank"),
        ]
        indexes = [models.Index(fields=["assignee", "status", "deadline"])]

    def __str__(self):
        return self.title
