from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class ImmutableError(Exception):
    pass


class AuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ImmutableError("Audit entries cannot be changed.")

    def delete(self):
        raise ImmutableError("Audit entries cannot be deleted.")

    def bulk_update(self, *args, **kwargs):
        raise ImmutableError("Audit entries cannot be changed.")


class AuditEntry(models.Model):
    """Append-only history of a record: who did what, when, and from which value to which."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    object_id = models.PositiveBigIntegerField()
    action = models.CharField(max_length=60)  # a short key such as "created" or "status_changed"; the screen translates it
    from_value = models.CharField(max_length=200, blank=True)
    to_value = models.CharField(max_length=200, blank=True)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    objects = AuditQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["content_type", "object_id", "created_at"])]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ImmutableError("Audit entries cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableError("Audit entries cannot be deleted.")


def record(actor, obj, action, from_value="", to_value="", comment=""):
    """Write one line in the record's history. Call it in the same transaction as the change itself."""
    return AuditEntry.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        content_type=ContentType.objects.get_for_model(obj.__class__),
        object_id=obj.pk,
        action=action,
        from_value=str(from_value or ""),
        to_value=str(to_value or ""),
        comment=comment or "",
    )


FORBIDDEN_DETAIL_WORDS = ("password", "passwd", "secret", "token", "authorization", "cookie", "csrf", "api_key", "private_key")


class SecurityEvent(models.Model):
    """Append-only trail of sign-ins and account changes: who did it, to whom, from where.

    `detail` may hold plain facts (the role someone moved to, the language chosen). It refuses anything that looks like a secret,
    by name and by shape, so a password or token cannot end up here by accident.
    """

    event = models.CharField(max_length=40, db_index=True)  # login_success, login_failed, password_changed, user_created ...
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="+", null=True, blank=True)
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="+", null=True, blank=True)
    identifier = models.CharField(max_length=254, blank=True)  # what was typed at sign-in, for failures against unknown accounts
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    objects = AuditQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["target", "created_at"]), models.Index(fields=["actor", "created_at"])]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ImmutableError("Security events cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableError("Security events cannot be deleted.")
