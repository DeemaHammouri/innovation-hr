"""Handover and Project endpoints and their serializers.

The serializers are WHITELISTS: every field is named, and nothing is read from the contract, the quotation or any payment record, so a
price can never reach Operation by accident (`operations/tests_privacy.py` walks every endpoint Operation can open to prove it)."""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from core.pagination import StandardPagination
from core.redact import RedactFreeText

from . import handover as svc
from . import staffing
from .models import Handover, Project

H = Handover.Status


def visible_q(user):
    if not user.has_capability("handover.view"):
        return Q(pk__in=[])
    if user.has_capability("operation.work"):  # Operation sees a handover once Commercial has submitted it
        return Q(status__in=[H.SUBMITTED, H.ESCALATED, H.ACCEPTED, H.RETURNED])
    if user.has_capability("handover.decide") or user.has_capability("lead.manage"):
        return Q()
    return Q(prepared_by=user) | Q(contract__lead__assigned_to=user)


def flags(user, h):
    open_for_decision = h.status in (H.SUBMITTED, H.ESCALATED)
    return {
        "can_edit": h.status in (H.DRAFT, H.RETURNED) and svc.can_write(user, h),
        "can_submit": h.status in (H.DRAFT, H.RETURNED) and svc.can_write(user, h),
        "can_accept": open_for_decision and user.has_capability("handover.decide"),
        "can_return": open_for_decision and user.has_capability("handover.decide"),
        "can_escalate": h.status == H.SUBMITTED and user.has_capability("operation.manage"),
    }


class HandoverSerializer(RedactFreeText, serializers.ModelSerializer):
    redacted_fields = ("services", "scope_notes", "contacts", "special_requirements", "decision_comment", "escalation_reason")
    client_name = serializers.CharField(source="client.company_name", read_only=True)
    contact_person = serializers.CharField(source="client.contact_person", read_only=True)
    phone = serializers.CharField(source="client.phone", read_only=True)
    email = serializers.CharField(source="client.email", read_only=True)
    prepared_by_name = serializers.CharField(source="prepared_by.full_name", read_only=True)
    decided_by_name = serializers.CharField(source="decided_by.full_name", default=None, read_only=True)
    escalated_by_name = serializers.CharField(source="escalated_by.full_name", default=None, read_only=True)
    project = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Handover
        fields = [
            "id", "ref", "status", "client", "client_name", "contact_person", "phone", "email", "prepared_by_name", "services", "scope_notes", "contacts",
            "special_requirements", "start_date", "submitted_at", "decided_by_name", "decided_at", "decision_comment", "escalated_by_name", "escalated_at",
            "escalation_reason", "project", "permissions", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_project(self, h):
        p = getattr(h, "project", None)
        return {"id": p.pk, "ref": p.ref} if p else None

    def get_permissions(self, h):
        return flags(self.context["request"].user, h)


class ProjectSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.company_name", read_only=True)
    handover_ref = serializers.CharField(source="handover.ref", read_only=True)
    handover_id = serializers.IntegerField(source="handover.pk", read_only=True)
    staff = serializers.SerializerMethodField()
    can_staff = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ["id", "ref", "name", "status", "client", "client_name", "handover_id", "handover_ref", "start_date", "created_at", "staff", "can_staff"]
        read_only_fields = fields

    def get_staff(self, p):
        return [
            {"user": r.user_id, "name": r.user.full_name, "role": r.role, "since": r.assigned_at, "ended_at": r.ended_at, "end_reason": r.end_reason}
            for r in p.staff.all()
        ]

    def get_can_staff(self, p):
        return p.status != "closed" and self.context["request"].user.has_capability("project.staff")


class HandoverViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    required_capabilities = {
        "*": ["handover.view"], "save": ["handover.view", "handover.write"], "submit": ["handover.view", "handover.write"],
        "accept": ["handover.view", "handover.decide"], "send_back": ["handover.view", "handover.decide"], "escalate": ["handover.view", "operation.manage"],
    }
    denied_message = "You don't have access to handovers."
    serializer_class = HandoverSerializer
    pagination_class = StandardPagination
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["ref", "client__company_name"]
    filterset_fields = ["status"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Handover.objects.none()
        return Handover.objects.filter(visible_q(self.request.user)).select_related("client", "prepared_by", "decided_by", "escalated_by", "project")

    def one(self, pk):
        return get_object_or_404(self.get_queryset(), pk=pk)

    def out(self, h):
        return Response(self.get_serializer(self.get_queryset().get(pk=h.pk)).data)

    @action(detail=True, methods=["post"], url_path="save")
    def save(self, request, pk=None):
        return self.out(svc.save(request.user, self.one(pk), request.data))

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        return self.out(svc.submit(request.user, self.one(pk)))

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        return self.out(svc.accept(request.user, self.one(pk)))

    @action(detail=True, methods=["post"], url_path="return")
    def send_back(self, request, pk=None):
        return self.out(svc.send_back(request.user, self.one(pk), request.data.get("comment")))

    @action(detail=True, methods=["post"])
    def escalate(self, request, pk=None):
        return self.out(svc.escalate(request.user, self.one(pk), request.data.get("reason")))


class ProjectViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    required_capabilities = {"*": ["project.view"], "primary": ["project.view", "project.staff"], "support": ["project.view", "project.staff"], "remove": ["project.view", "project.staff"]}
    denied_message = "You don't have access to projects."
    serializer_class = ProjectSerializer
    pagination_class = StandardPagination
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["ref", "name", "client__company_name"]
    filterset_fields = ["status"]

    def get_queryset(self):
        return Project.objects.select_related("client", "handover").prefetch_related("staff__user")

    def _staffed(self, project):
        return Response(ProjectSerializer(self.get_queryset().get(pk=project.pk), context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="primary")
    def primary(self, request, pk=None):
        return self._staffed(staffing.assign_primary(request.user, self.get_object(), request.data.get("user"), request.data.get("reason")))

    @action(detail=True, methods=["post"], url_path="support")
    def support(self, request, pk=None):
        return self._staffed(staffing.add_support(request.user, self.get_object(), request.data.get("user")))

    @action(detail=True, methods=["post"], url_path="remove")
    def remove(self, request, pk=None):
        return self._staffed(staffing.remove_support(request.user, self.get_object(), request.data.get("user"), request.data.get("reason")))
