from rest_framework import serializers

from .models import Client


class ClientSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    lead_ref = serializers.CharField(source="lead.ref", default=None, read_only=True)

    class Meta:
        model = Client
        fields = [
            "id", "company_name", "contact_person", "phone", "email", "address", "notes",
            "status", "lead", "lead_ref", "portal_status", "created_by", "created_by_name", "created_at", "updated_at",
        ]
        read_only_fields = ["status", "lead", "portal_status", "created_by", "created_at", "updated_at"]

    def validate_company_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter the company name.")
        return value
