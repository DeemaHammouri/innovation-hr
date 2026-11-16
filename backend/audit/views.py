from rest_framework import serializers
from rest_framework.generics import ListAPIView

from core import access
from core.pagination import StandardPagination

from .models import AuditEntry


class AuditEntrySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", default=None, read_only=True)

    class Meta:
        model = AuditEntry
        fields = ["id", "actor", "actor_name", "action", "from_value", "to_value", "comment", "created_at"]
        read_only_fields = fields


class ActivityListView(ListAPIView):
    required_capabilities = []  # any signed-in person; access to the record itself is checked in core.access
    """GET /api/activity/?target=client:5 : the read-only timeline of one record. Read-only by design: there is no write endpoint."""

    serializer_class = AuditEntrySerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        _, obj = access.resolve(self.request.user, self.request.query_params.get("target"))
        return AuditEntry.objects.filter(content_type=access.content_type_for(obj), object_id=obj.pk).select_related("actor")
