from django.db import models, transaction


class Sequence(models.Model):
    """Counter behind readable references such as LD-0001."""

    prefix = models.CharField(max_length=8, unique=True)
    last = models.PositiveIntegerField(default=0)

    @classmethod
    def next_ref(cls, prefix):
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(prefix=prefix)
            seq.last += 1
            seq.save(update_fields=["last"])
            return f"{prefix}-{seq.last:04d}"


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Archivable(models.Model):
    """Business records are archived, never deleted."""

    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        abstract = True

    @property
    def is_archived(self):
        return self.archived_at is not None
