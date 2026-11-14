from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import TimeStamped

OPEN = ["requested", "in_preparation", "in_review", "changes_requested", "signed", "sent", "waiting"]


class Quotation(TimeStamped):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        IN_PREPARATION = "in_preparation", "In preparation"
        IN_REVIEW = "in_review", "In review"
        CHANGES_REQUESTED = "changes_requested", "Changes requested"
        SIGNED = "signed", "Signed"
        SENT = "sent", "Sent to client"
        WAITING = "waiting", "Waiting"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    ref = models.CharField(max_length=12, unique=True)
    lead = models.ForeignKey("leads.Lead", on_delete=models.PROTECT, related_name="quotations")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="quotations_requested")
    request_note = models.TextField(blank=True)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="quotations_prepared", null=True, blank=True)
    review_comment = models.TextField(blank=True)
    signed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="quotations_signed", null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    signed_version = models.PositiveIntegerField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    next_follow_up = models.DateField(null=True, blank=True, db_index=True)
    rejection_reason = models.ForeignKey("lookups.RejectionReason", on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    rejection_note = models.TextField(blank=True)
    outcome_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            # A lead has at most one quotation in progress. A rejected or cancelled one frees the lead for a new request.
            models.UniqueConstraint(fields=["lead"], condition=Q(status__in=OPEN), name="quotations_one_open_per_lead"),
        ]

    def __str__(self):
        return self.ref


class QuotationVersion(TimeStamped):
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="JOD")
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    submitted_at = models.DateTimeField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["quotation", "number"], name="quotation_version_number_unique"),
            models.CheckConstraint(condition=Q(number__gte=1), name="quotation_version_number_positive"),
            models.CheckConstraint(condition=Q(total__gte=0), name="quotation_version_total_not_negative"),
        ]


class QuotationLine(models.Model):
    version = models.ForeignKey(QuotationVersion, on_delete=models.CASCADE, related_name="lines")
    position = models.PositiveIntegerField(default=0)
    service = models.ForeignKey("lookups.Service", on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1"))
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="quotation_line_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="quotation_line_price_not_negative"),
            models.CheckConstraint(condition=Q(discount_percent__gte=0, discount_percent__lte=100), name="quotation_line_discount_range"),
            models.CheckConstraint(condition=Q(tax_percent__gte=0, tax_percent__lte=100), name="quotation_line_tax_range"),
        ]
