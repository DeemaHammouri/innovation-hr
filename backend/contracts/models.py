from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import TimeStamped

OPEN = ["requested", "drafting", "with_commercial", "meeting_logged", "ceo_review", "returned", "signed"]


class Contract(TimeStamped):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        DRAFTING = "drafting", "Drafting"
        WITH_COMMERCIAL = "with_commercial", "With Commercial"
        MEETING_LOGGED = "meeting_logged", "Meeting logged"
        CEO_REVIEW = "ceo_review", "CEO review"
        RETURNED = "returned", "Returned by CEO"
        SIGNED = "signed", "Signed by CEO"
        HANDED_OVER = "handed_over", "Handed over"
        CANCELLED = "cancelled", "Cancelled"

    ref = models.CharField(max_length=20, unique=True)
    lead = models.ForeignKey("leads.Lead", on_delete=models.PROTECT, related_name="contracts")
    quotation = models.ForeignKey("quotations.Quotation", null=True, blank=True, on_delete=models.PROTECT, related_name="contracts")
    client = models.ForeignKey("clients.Client", null=True, blank=True, on_delete=models.PROTECT, related_name="contracts")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    request_note = models.TextField(blank=True)
    drafted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    meeting_date = models.DateField(null=True, blank=True)
    meeting_notes = models.TextField(blank=True)
    meeting_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    submitted_to_ceo_at = models.DateTimeField(null=True, blank=True)
    ceo_comment = models.TextField(blank=True)
    signed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    signed_at = models.DateTimeField(null=True, blank=True)
    handed_over_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    handed_over_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["lead"], condition=Q(status__in=OPEN), name="contracts_one_open_per_lead"),
        ]

    def __str__(self):
        return self.ref


class ContractVersion(TimeStamped):
    """One draft sent to Commercial. The files themselves are attachments of the contract with category "draft"."""

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["contract", "number"], name="contract_version_number_unique"),
            models.CheckConstraint(condition=Q(number__gte=1), name="contract_version_number_positive"),
        ]
