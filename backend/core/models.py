from django.db import models, transaction

from .fields import UpdatedAtField


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


class YearSequence(models.Model):
    """Counter that starts again every year, behind numbers such as PREFIX/2026/3/0007.

    The number is taken inside the same transaction that uses it and the row is locked while it is taken, so two people sending at once
    never get the same number, and a failed send gives its number back (no gaps)."""

    key = models.CharField(max_length=20)
    year = models.PositiveIntegerField()
    last = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["key", "year"], name="core_yearsequence_key_year")]

    @classmethod
    def next_number(cls, key, prefix, when):
        """`when` is a local date. Returns PREFIX/YYYY/M/NNNN. Call inside transaction.atomic()."""
        seq, _ = cls.objects.select_for_update().get_or_create(key=key, year=when.year)
        seq.last += 1
        seq.save(update_fields=["last"])
        return f"{prefix}/{when.year}/{when.month}/{seq.last:04d}"


def private_file_storage():
    from files.models import private_storage

    return private_storage


def stamp_name(instance, filename):
    import uuid

    return f"company/{uuid.uuid4().hex}.png"


class CompanyProfile(models.Model):
    """The one row of company details that documents use: names, the stamp, and the prefixes of the yearly numbers."""

    name_en = models.CharField(max_length=120, default="Innovation Accounting Solutions")
    name_ar = models.CharField(max_length=120, default="إنوفيشن لحلول المحاسبة")
    quotation_prefix = models.CharField(max_length=12, default="QT")
    contract_prefix = models.CharField(max_length=12, default="CT")
    stamp = models.FileField(storage=private_file_storage, upload_to=stamp_name, max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class DailyRun(models.Model):
    """Marks that a named daily job already ran for a local date, so it never runs twice in a day."""

    name = models.CharField(max_length=60)
    day = models.DateField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["name", "day"], name="core_dailyrun_once_per_day")]


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = UpdatedAtField()

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
