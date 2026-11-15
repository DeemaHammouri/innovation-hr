from rest_framework import serializers

from . import access, sla
from .models import ImportBatch, Interaction, Lead


class LeadSerializer(serializers.ModelSerializer):
    """Reads. The view puts `request`, `today`, `now` and `sla` in the context once, so a list costs no extra queries per row."""

    assigned_to_name = serializers.CharField(source="assigned_to.full_name", default=None, read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    batch_ref = serializers.CharField(source="batch.ref", default=None, read_only=True)
    rejection_reason_en = serializers.CharField(source="rejection_reason.name_en", default=None, read_only=True)
    rejection_reason_ar = serializers.CharField(source="rejection_reason.name_ar", default=None, read_only=True)
    follow_up_overdue = serializers.SerializerMethodField()
    first_contact_overdue = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    quotation = serializers.SerializerMethodField()
    contract = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id", "ref", "company_name", "contact_name", "phone", "email", "source", "notes", "status",
            "assigned_to", "assigned_to_name", "assigned_at", "batch", "batch_ref", "created_by", "created_by_name", "created_at",
            "next_follow_up", "rejection_reason", "rejection_reason_en", "rejection_reason_ar", "rejection_note",
            "first_contacted_at", "last_contacted_at", "qualified_at", "rejected_at", "archived_at", "archive_reason",
            "follow_up_overdue", "first_contact_overdue", "permissions", "quotation", "contract", "skipped_quotation_at", "updated_at",
        ]
        read_only_fields = fields

    def _clock(self):
        ctx = self.context
        if "today" not in ctx:
            ctx["today"], ctx["now"], ctx["sla"] = sla.sla_now()
        return ctx["today"], ctx["now"], ctx["sla"]

    def get_follow_up_overdue(self, lead):
        return sla.follow_up_overdue(lead, self._clock()[0])

    def get_first_contact_overdue(self, lead):
        _, now, setting = self._clock()
        return sla.first_contact_overdue(lead, now, setting)

    def get_permissions(self, lead):
        return access.flags(self.context["request"].user, lead)

    def get_quotation(self, lead):
        """The lead's newest quotation (from the prefetched list), so the lead page can link to it."""
        items = list(lead.quotations.all())
        if not items:
            return None
        q = max(items, key=lambda x: x.pk)
        return {"id": q.pk, "ref": q.ref, "status": q.status}


    def get_contract(self, lead):
        items = list(lead.contracts.all())
        if not items:
            return None
        c = max(items, key=lambda x: x.pk)
        return {"id": c.pk, "ref": c.ref, "status": c.status}


class InteractionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = Interaction
        fields = ["id", "type", "occurred_at", "notes", "outcome", "created_by", "created_by_name", "created_at"]
        read_only_fields = fields


class ContactInputSerializer(serializers.Serializer):
    """Body of 'log a contact' and 'record an outcome'. The rules live in services.py."""

    type = serializers.CharField(required=False, allow_blank=True, default="call")
    occurred_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")
    outcome = serializers.CharField(required=False, allow_blank=True, default="")
    next_follow_up = serializers.DateField(required=False, allow_null=True)
    rejection_reason = serializers.IntegerField(required=False, allow_null=True)
    rejection_note = serializers.CharField(required=False, allow_blank=True, max_length=1000, default="")


class ImportBatchSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    contacted_count = serializers.SerializerMethodField()
    can_undo = serializers.SerializerMethodField()

    class Meta:
        model = ImportBatch
        fields = [
            "id", "ref", "filename", "status", "total_rows", "imported_count", "skipped_errors", "skipped_duplicates",
            "created_by", "created_by_name", "created_at", "undone_at", "contacted_count", "can_undo",
        ]
        read_only_fields = fields

    def get_contacted_count(self, batch):
        return getattr(batch, "contacted_n", None) if hasattr(batch, "contacted_n") else batch.leads.exclude(status="new").count()

    def get_can_undo(self, batch):
        user = self.context["request"].user
        return batch.status == "active" and batch.created_by_id == user.pk and self.get_contacted_count(batch) == 0
