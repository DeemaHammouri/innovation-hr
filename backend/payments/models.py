"""
Payments: an instalment schedule per client, payments recorded against instalments, and reversal entries.

Nothing is ever edited or deleted once recorded: a mistaken payment is cancelled by a reversal row that points at it.
An instalment's status is never stored. It is computed from its payments and today's date.
"""
from django.conf import settings
from django.db import models

from clients.models import Client
from core.models import TimeStamped


class LedgerError(Exception):
    pass


class LedgerQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise LedgerError("Payment records cannot be changed.")

    def delete(self):
        raise LedgerError("Payment records cannot be deleted.")


class Instalment(TimeStamped):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="instalments")
    contract = models.ForeignKey("contracts.Contract", on_delete=models.PROTECT, null=True, blank=True, related_name="instalments")
    number = models.PositiveSmallIntegerField()
    due_date = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="JOD")
    note = models.CharField(max_length=200, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=300, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["due_date", "number", "id"]
        indexes = [models.Index(fields=["client", "due_date"])]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="instalment_amount_positive"),
            models.CheckConstraint(condition=models.Q(cancelled_at__isnull=True) | ~models.Q(cancel_reason=""), name="instalment_cancel_needs_reason"),
            models.UniqueConstraint(fields=["client", "number"], name="instalment_unique_number_per_client"),
        ]

    def __str__(self):
        return f"{self.client_id}#{self.number}"


class Payment(models.Model):
    class Kind(models.TextChoices):
        PAYMENT = "payment", "Payment"
        REVERSAL = "reversal", "Reversal"

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        BANK = "bank_transfer", "Bank transfer"
        CHEQUE = "cheque", "Cheque"
        CARD = "card", "Card"
        OTHER = "other", "Other"

    instalment = models.ForeignKey(Instalment, on_delete=models.PROTECT, related_name="payments")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PAYMENT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # always positive; a reversal subtracts it
    received_on = models.DateField(db_index=True)
    method = models.CharField(max_length=14, choices=Method.choices, default=Method.BANK)
    reference = models.CharField(max_length=100, blank=True)
    note = models.CharField(max_length=300, blank=True)
    reverses = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversal")
    reason = models.CharField(max_length=300, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = LedgerQuerySet.as_manager()

    class Meta:
        ordering = ["-received_on", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="payment_amount_positive"),
            models.CheckConstraint(
                condition=models.Q(kind="payment", reverses__isnull=True) | (models.Q(kind="reversal", reverses__isnull=False) & ~models.Q(reason="")),
                name="payment_reversal_shape",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise LedgerError("Payment records cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise LedgerError("Payment records cannot be deleted.")

    @property
    def signed_amount(self):
        return self.amount if self.kind == self.Kind.PAYMENT else -self.amount
