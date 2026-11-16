from django.utils import timezone
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardPagination

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "body", "link", "created_at", "read"]
        read_only_fields = fields

    def get_read(self, n):
        return n.read_at is not None


class NotificationListView(ListAPIView):
    required_capabilities = []  # any signed-in person; access to the record itself is checked in core.access
    """Only ever the signed-in person's own notifications."""

    serializer_class = NotificationSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)
        if self.request.query_params.get("unread") == "1":
            qs = qs.filter(read_at__isnull=True)
        return qs


class UnreadCountView(APIView):
    required_capabilities = []  # any signed-in person; access to the record itself is checked in core.access
    def get(self, request):
        return Response({"count": Notification.objects.filter(user=request.user, read_at__isnull=True).count()})


class MarkReadView(APIView):
    required_capabilities = []  # any signed-in person; access to the record itself is checked in core.access
    def post(self, request, pk):
        updated = Notification.objects.filter(user=request.user, pk=pk, read_at__isnull=True).update(read_at=timezone.now())
        if not updated and not Notification.objects.filter(user=request.user, pk=pk).exists():
            return Response({"detail": "Notification not found."}, status=404)
        return Response(status=204)


class MarkAllReadView(APIView):
    required_capabilities = []  # any signed-in person; access to the record itself is checked in core.access
    def post(self, request):
        Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
        return Response(status=204)
