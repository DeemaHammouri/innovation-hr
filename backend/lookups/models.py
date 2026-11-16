from django.db import models


class Bilingual(models.Model):
    name_en = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True, db_index=True)  # lookups are switched off, never deleted
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name_en


class RejectionReason(Bilingual):
    pass


class Service(Bilingual):
    default_unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="JOD")


class ChecklistTemplateItem(Bilingual):
    """The legal / KYC checklist a new client starts with. Operation can customise it per client later."""

    required = models.BooleanField(default=True)
    has_expiry = models.BooleanField(default=False)  # the document runs out (a licence, a certificate): verifying it asks for the expiry date


class Singleton(models.Model):
    class Meta:
        abstract = True

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class WorkHours(Singleton):
    """Attendance rules. Lateness is judged against these."""

    work_start = models.TimeField(default="09:00")
    work_end = models.TimeField(default="17:00")
    grace_minutes = models.PositiveSmallIntegerField(default=15)


class SlaSetting(Singleton):
    """How long a lead may wait before someone acts."""

    first_contact_hours = models.PositiveSmallIntegerField(default=48)
    follow_up_days = models.PositiveSmallIntegerField(default=3)  # suggested gap before the next follow-up
