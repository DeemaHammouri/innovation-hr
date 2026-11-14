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


    @classmethod
    def reserve(cls, prefix, count):
        """Hand out `count` consecutive references in one step (used by imports)."""
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(prefix=prefix)
            first = seq.last + 1
            seq.last += count
            seq.save(update_fields=["last"])
            return [f"{prefix}-{n:04d}" for n in range(first, first + count)]


class DailyRun(models.Model):
    """Marks that a named daily job already ran for a local date, so it never runs twice in a day."""

    name = models.CharField(max_length=60)
    day = models.DateField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["name", "day"], name="core_dailyrun_once_per_day")]


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
