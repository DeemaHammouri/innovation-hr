from rest_framework import serializers

from core.redact import RedactFreeText

from .models import Client


class ClientSerializer(RedactFreeText, serializers.ModelSerializer):
    redacted_fields = ("notes", "decision_note")  # Operation never reads a price typed into a note
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    lead_ref = serializers.CharField(source="lead.ref", default=None, read_only=True)

    class Meta:
        model = Client
        fields = [
            "id", "company_name", "contact_person", "phone", "email", "address", "notes",
            "status", "country", "decision", "decision_at", "decision_follow_up", "decision_note", "lead", "lead_ref", "portal_status", "created_by", "created_by_name", "created_at", "updated_at",
        ]
        read_only_fields = ["status", "decision", "decision_at", "decision_follow_up", "decision_note", "lead", "portal_status", "created_by", "created_at", "updated_at"]

    def validate_country(self, value):
        from .countries import CODES

        if value not in CODES:
            raise serializers.ValidationError("Choose a country from the list.")
        return value

    def validate_company_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter the company name.")
        return value
