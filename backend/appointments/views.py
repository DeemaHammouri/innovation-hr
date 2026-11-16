from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import User
from core.pagination import StandardPagination

from . import services
from .models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    lead_ref = serializers.CharField(source="lead.ref", default=None, read_only=True)
    lead_company = serializers.CharField(source="lead.company_name", default=None, read_only=True)
    owner_name = serializers.CharField(source="owner.full_name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    overdue = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id", "type", "title", "lead", "lead_ref", "lead_company", "owner", "owner_name", "created_by", "created_by_name",
            "starts_at", "ends_at", "notes", "status", "closed_at", "cancel_reason", "overdue", "permissions", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_overdue(self, a):
        return a.status == "scheduled" and a.starts_at < timezone.now()

    def get_permissions(self, a):
        user = self.context["request"].user
        open_ = a.status == "scheduled" and services.can_manage(user, a)
        report = getattr(a, "report", None)
        done_with_lead = a.status == "done" and a.lead_id is not None
        writer = user.has_capability("meeting_report.write") and (services.can_manage(user, a) or user.has_capability("meeting_report.view_all"))
        can_see = report is not None and (
            user.has_capability("meeting_report.view_all") or report.author_id == user.pk
            or (user.has_capability("lead.view_assigned") and a.lead is not None and a.lead.assigned_to_id == user.pk)
        )
        return {
            "can_edit": open_, "can_reschedule": open_, "can_complete": open_, "can_cancel": open_,
            "can_write_report": bool(done_with_lead and writer and report is None),
            "report_id": report.pk if can_see else None,
        }


class AppointmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Your own appointments. The Commercial head also gives them to people and sees everyone's; the CEO sees everyone's."""

    required_capabilities = {"*": ["appointment.access"], "assignees": ["appointment.access", "appointment.assign"]}
    denied_message = {"*": "You don't have access to appointments.", "assignees": "Only the Commercial head can do this."}
    serializer_class = AppointmentSerializer
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        qs = Appointment.objects.select_related("lead", "owner", "created_by", "report")
        if not user.has_capability("appointment.view_all"):
            qs = qs.filter(Q(owner=user) | Q(created_by=user))
        return qs

    def filter_queryset(self, qs):
        p = self.request.query_params
        if p.get("owner", "").isdigit():
            qs = qs.filter(owner_id=int(p["owner"]))
        elif p.get("scope") == "mine":
            qs = qs.filter(owner=self.request.user)
        if p.get("type") in Appointment.Type.values:
            qs = qs.filter(type=p["type"])
        if p.get("status") in Appointment.Status.values:
            qs = qs.filter(status=p["status"])
        if p.get("lead", "").isdigit():
            qs = qs.filter(lead_id=int(p["lead"]))
        start, end = parse_date(p.get("from", "")), parse_date(p.get("to", ""))
        if start:
            qs = qs.filter(starts_at__date__gte=start)
        if end:
            qs = qs.filter(starts_at__date__lte=end)
        return qs

    def out(self, appt, code=200):
        return Response(self.get_serializer(self.get_queryset().get(pk=appt.pk)).data, status=code)

    def create(self, request, *args, **kwargs):
        return self.out(services.create(request.user, request.data), 201)

    def partial_update(self, request, *args, **kwargs):
        return self.out(services.update(request.user, self.get_object(), request.data))

    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        return self.out(services.reschedule(request.user, self.get_object(), request.data.get("starts_at"), request.data.get("ends_at")))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self.out(services.cancel(request.user, self.get_object(), request.data.get("reason", "")))

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return self.out(services.complete(request.user, self.get_object()))

    @action(detail=False, methods=["get"])
    def assignees(self, request):
        people = [u for u in User.objects.filter(is_active=True).order_by("full_name") if services.eligible_owner(u)]
        return Response([{"id": u.pk, "full_name": u.full_name} for u in people])
