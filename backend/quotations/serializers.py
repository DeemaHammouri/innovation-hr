from rest_framework import serializers

from . import access
from .models import Quotation, QuotationLine, QuotationVersion


class LineSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationLine
        fields = ["id", "position", "service", "description", "quantity", "unit_price", "discount_percent", "tax_percent", "line_total"]
        read_only_fields = fields


class VersionSerializer(serializers.ModelSerializer):
    lines = LineSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    is_draft = serializers.SerializerMethodField()

    class Meta:
        model = QuotationVersion
        fields = [
            "id", "number", "currency", "valid_until", "notes", "created_by_name", "created_at", "submitted_at", "is_draft",
            "subtotal", "discount_total", "tax_total", "total", "lines",
        ]
        read_only_fields = fields

    def get_is_draft(self, v):
        return v.submitted_at is None


class QuotationSerializer(serializers.ModelSerializer):
    """List rows: no lines. `latest` is the newest version's number and total, read from the prefetched versions, so a page costs no extra queries."""

    lead_ref = serializers.CharField(source="lead.ref", read_only=True)
    lead_company = serializers.CharField(source="lead.company_name", read_only=True)
    lead_contact = serializers.CharField(source="lead.contact_name", read_only=True)
    assigned_to_name = serializers.CharField(source="lead.assigned_to.full_name", default=None, read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.full_name", read_only=True)
    prepared_by_name = serializers.CharField(source="prepared_by.full_name", default=None, read_only=True)
    signed_by_name = serializers.CharField(source="signed_by.full_name", default=None, read_only=True)
    rejection_reason_en = serializers.CharField(source="rejection_reason.name_en", default=None, read_only=True)
    rejection_reason_ar = serializers.CharField(source="rejection_reason.name_ar", default=None, read_only=True)
    latest = serializers.SerializerMethodField()
    follow_up_overdue = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Quotation
        fields = [
            "id", "ref", "lead", "lead_ref", "lead_company", "lead_contact", "assigned_to_name", "status", "requested_by", "requested_by_name",
            "request_note", "prepared_by_name", "review_comment", "signed_by_name", "signed_at", "signed_version", "sent_at", "next_follow_up",
            "rejection_reason", "rejection_reason_en", "rejection_reason_ar", "rejection_note", "outcome_at", "cancel_reason", "created_at",
            "latest", "follow_up_overdue", "permissions",
        ]
        read_only_fields = fields

    def get_latest(self, q):
        versions = list(q.versions.all())
        if not versions:
            return None
        v = max(versions, key=lambda x: x.number)
        shown = next((x for x in versions if x.number == q.signed_version), v) if q.signed_version else v
        return {"number": v.number, "is_draft": v.submitted_at is None, "currency": shown.currency, "total": str(shown.total), "valid_until": shown.valid_until, "count": len(versions)}

    def get_follow_up_overdue(self, q):
        today = self.context.get("today")
        return bool(q.status == "waiting" and q.next_follow_up and today and q.next_follow_up < today)

    def get_permissions(self, q):
        return access.flags(self.context["request"].user, q)


class QuotationDetailSerializer(QuotationSerializer):
    versions = VersionSerializer(many=True, read_only=True)

    class Meta(QuotationSerializer.Meta):
        fields = QuotationSerializer.Meta.fields + ["versions"]
        read_only_fields = fields
