from files.models import Attachment
from core.access import content_type_for
from rest_framework import serializers

from . import access, services
from .models import Instalment, Payment


def money(value):
    return f"{value:.2f}"


class InstalmentSerializer(serializers.ModelSerializer):
    """Expects the instalment to be annotated with `paid` (services.with_paid) and `today` in the context."""

    status = serializers.SerializerMethodField()
    paid = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    contract_ref = serializers.CharField(source="contract.ref", default=None, read_only=True)

    class Meta:
        model = Instalment
        fields = ["id", "client", "contract", "contract_ref", "number", "due_date", "amount", "currency", "note", "status", "paid", "balance", "cancelled_at", "cancel_reason", "can_edit"]
        read_only_fields = fields

    def get_status(self, i):
        return services.status_of(i, i.paid, self.context["today"])

    def get_paid(self, i):
        return money(i.paid)

    def get_balance(self, i):
        return money(max(i.amount - i.paid, 0)) if not i.cancelled_at else "0.00"

    def get_amount(self, i):
        return money(i.amount)

    def get_can_edit(self, i):
        return not i.cancelled_at and i.n_payments == 0 and access.can_write(self.context["request"].user)


class PaymentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source="recorded_by.full_name", read_only=True)
    amount = serializers.SerializerMethodField()
    instalment_number = serializers.IntegerField(source="instalment.number", read_only=True)
    currency = serializers.CharField(source="instalment.currency", read_only=True)
    reversed = serializers.SerializerMethodField()
    has_receipt = serializers.SerializerMethodField()
    can_reverse = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "instalment", "instalment_number", "kind", "amount", "currency", "received_on", "method", "reference", "note",
            "reverses", "reason", "recorded_by_name", "created_at", "reversed", "has_receipt", "can_reverse",
        ]
        read_only_fields = fields

    def get_amount(self, p):
        return money(p.amount)

    def get_reversed(self, p):
        return p.kind == Payment.Kind.PAYMENT and hasattr(p, "reversal")

    def get_has_receipt(self, p):
        receipts = self.context.get("receipts")
        if receipts is not None:
            return p.pk in receipts
        return Attachment.objects.filter(content_type=content_type_for(Payment), object_id=p.pk, archived_at__isnull=True).exists()

    def get_can_reverse(self, p):
        return access.can_write(self.context["request"].user) and p.kind == Payment.Kind.PAYMENT and not hasattr(p, "reversal")


def receipt_ids(payments):
    ids = [p.pk for p in payments]
    return set(Attachment.objects.filter(content_type=content_type_for(Payment), object_id__in=ids, archived_at__isnull=True).values_list("object_id", flat=True))
