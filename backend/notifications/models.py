from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """In-app only. `kind` + `params` are what the notification says; the text is written in the reader's language when it is read.
    `title` and `body` hold the text as first written (in the recipient's language then) and are what old rows without `params` show."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=60)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=400, blank=True)
    link = models.CharField(max_length=200, blank=True)  # a frontend path, e.g. /leads/4
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=120, blank=True, db_index=True)  # lets reminders (overdue) fire once
    params = models.JSONField(null=True, blank=True)  # the values of the message placeholders; null on rows made before this existed

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "read_at", "created_at"])]
        constraints = [
            # One notification per (person, key): the database settles two callers that both passed the exists() check.
            models.UniqueConstraint(fields=["user", "dedupe_key"], condition=~models.Q(dedupe_key=""), name="notification_unique_dedupe_key"),
        ]
