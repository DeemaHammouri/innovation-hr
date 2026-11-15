from core.concurrency import check_fresh
from rest_framework import mixins, viewsets
from rest_framework.filters import SearchFilter

from audit.models import record
from accounts.permissions import CanManageClients, PasswordChangeNotPending

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

    permission_classes = [CanManageClients, PasswordChangeNotPending]
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
