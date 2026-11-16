from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import TimeStamped
from files.models import private_storage, stored_name

OPEN = ["requested", "drafting", "with_commercial", "confirmed", "sent", "ceo_review", "returned", "signed"]


class Contract(TimeStamped):
    """requested -> drafting (HR) -> with_commercial -> confirmed (Commercial head) -> sent (numbered) -> ceo_review (the client signed)
    -> signed (CEO, with signature and stamp or an uploaded final copy) -> handed_over.  The Commercial head can return it to HR from
    with_commercial.  (The old flow's `meeting_logged` state and `meeting_*` fields were removed by migration 0005; see there.)"""

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        DRAFTING = "drafting", "Drafting"
        WITH_COMMERCIAL = "with_commercial", "With Commercial"
        CONFIRMED = "confirmed", "Confirmed by Commercial"
        SENT = "sent", "Sent to client"
        CEO_REVIEW = "ceo_review", "Waiting for the CEO"
        RETURNED = "returned", "Returned to HR"
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
    submitted_to_ceo_at = models.DateTimeField(null=True, blank=True)
    ceo_comment = models.TextField(blank=True)
    signed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    signed_at = models.DateTimeField(null=True, blank=True)
    handed_over_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    handed_over_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True)
    country = models.CharField(max_length=5, default="JO")
    template = models.ForeignKey("contracts.ContractTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    returned_comment = models.TextField(blank=True)  # why Commercial sent it back to HR
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    number = models.CharField(max_length=40, unique=True, null=True, blank=True)  # CONTRACT PREFIX/YYYY/M/NNNN, issued when it is sent
    sent_at = models.DateTimeField(null=True, blank=True)
    client_signed_at = models.DateTimeField(null=True, blank=True)
    client_signed_via = models.CharField(max_length=10, blank=True)  # "", "portal", "upload"
    client_signed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    client_signature = models.FileField(storage=private_storage, upload_to=stored_name, max_length=255, blank=True)
    signature = models.FileField(storage=private_storage, upload_to=stored_name, max_length=255, blank=True)  # the CEO's drawn signature
    stamp = models.FileField(storage=private_storage, upload_to=stored_name, max_length=255, blank=True)
    signed_via = models.CharField(max_length=10, blank=True)  # "", "drawn", "upload" (a final copy uploaded by the CEO)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["created_at"], name="contract_created_idx")]
        constraints = [
            models.UniqueConstraint(fields=["lead"], condition=Q(status__in=OPEN), name="contracts_one_open_per_lead"),
        ]

    def __str__(self):
        return self.ref


class ContractVersion(TimeStamped):
    """One draft of the contract text. The latest version with no `submitted_at` is the draft HR is working on. Files that go with it
    (for example a Word draft) are attachments of the contract with category "draft"."""

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    title = models.CharField(max_length=200, blank=True)
    body_en = models.TextField(blank=True)
    body_ar = models.TextField(blank=True)
    currency = models.CharField(max_length=3, blank=True)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_terms = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    services = models.JSONField(default=list, blank=True)  # [{description, frequency, visits, quantity, unit_price, line_total}] copied from the quotation
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["contract", "number"], name="contract_version_number_unique"),
            models.CheckConstraint(condition=Q(number__gte=1), name="contract_version_number_positive"),
        ]


class ContractTemplate(TimeStamped):
    """The wording of a contract for one country. `country` is a code from clients.countries, or "*" for the template used when a country has none.

    Placeholders in the text are replaced when a contract is prepared: {client}, {company}, {country}, {date}, {total}, {currency},
    {payment_terms}, {start_date}, {end_date}, {services}."""

    country = models.CharField(max_length=5, unique=True)
    name_en = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120)
    body_en = models.TextField()
    body_ar = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["country"]

    def __str__(self):
        return f"{self.country}: {self.name_en}"
