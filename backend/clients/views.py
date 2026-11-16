from core.concurrency import check_fresh
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter

from audit.models import record

from . import services
from .models import Client
from .serializers import ClientSerializer


class ClientViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Create, read and edit. There is no delete in this version."""

    required_capabilities = {"*": ["client.manage"]}
    denied_message = "Only the Operation Manager and the CEO can manage clients."
    queryset = Client.objects.select_related("created_by")
    serializer_class = ClientSerializer
    filter_backends = [SearchFilter]
    search_fields = ["company_name", "contact_person", "email", "phone"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_create(self, serializer):
        client = serializer.save(created_by=self.request.user)
        record(self.request.user, client, "created")

    def perform_update(self, serializer):
        check_fresh(serializer.instance, self.request.data)
        changed = [f for f, v in serializer.validated_data.items() if getattr(serializer.instance, f) != v]
        client = serializer.save()
        if changed:
            record(self.request.user, client, "updated", to_value=", ".join(changed))

    @action(detail=True, methods=["post"])
    def portal(self, request, pk=None):
        """Open the client's portal (after fixing the email), or send a new temporary password if the first email did not arrive."""
        client = self.get_object()
        return Response({"portal_status": services.ensure_portal(client, request.user)})
