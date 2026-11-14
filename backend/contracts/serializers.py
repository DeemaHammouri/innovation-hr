from rest_framework import serializers

from . import access
from .models import Contract, ContractVersion


class VersionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = ContractVersion
        fields = ["id", "number", "note", "created_by_name", "created_at"]
        read_only_fields = fields


class ContractSerializer(serializers.ModelSerializer):
    lead_ref = serializers.CharField(source="lead.ref", read_only=True)
    lead_company = serializers.CharField(source="lead.company_name", read_only=True)
    lead_contact = serializers.CharField(source="lead.contact_name", read_only=True)
    assigned_to_name = serializers.CharField(source="lead.assigned_to.full_name", default=None, read_only=True)
    quotation_ref = serializers.CharField(source="quotation.ref", default=None, read_only=True)
    requested_by_name = serializers.CharField(source="requested_by.full_name", read_only=True)
    drafted_by_name = serializers.CharField(source="drafted_by.full_name", default=None, read_only=True)
    meeting_by_name = serializers.CharField(source="meeting_by.full_name", default=None, read_only=True)
    signed_by_name = serializers.CharField(source="signed_by.full_name", default=None, read_only=True)
    handed_over_by_name = serializers.CharField(source="handed_over_by.full_name", default=None, read_only=True)
    permissions = serializers.SerializerMethodField()
    attachable = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = [
            "id", "ref", "lead", "lead_ref", "lead_company", "lead_contact", "assigned_to_name", "quotation", "quotation_ref", "client", "status",
            "requested_by_name", "request_note", "drafted_by_name", "meeting_date", "meeting_notes", "meeting_by_name", "submitted_to_ceo_at",
            "ceo_comment", "signed_by_name", "signed_at", "handed_over_by_name", "handed_over_at", "cancel_reason", "created_at", "permissions", "attachable",
        ]
        read_only_fields = fields

    def get_permissions(self, c):
        return access.flags(self.context["request"].user, c)

    def get_attachable(self, c):
        """Which document slots this person may upload to right now. The server checks again on the upload itself."""
        user = self.context["request"].user
        return [cat for cat in ("draft", "visit_report", "client_signed_copy", "final_signed", "") if access.can_attach(user, c, cat)]


class ContractDetailSerializer(ContractSerializer):
    versions = VersionSerializer(many=True, read_only=True)

    class Meta(ContractSerializer.Meta):
        fields = ContractSerializer.Meta.fields + ["versions"]
        read_only_fields = fields
