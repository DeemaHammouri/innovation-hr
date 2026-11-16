from datetime import date

from django.db.models import Count, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from clients.models import Client
from core.pagination import StandardPagination
from leads.sla import sla_now

from . import access, services
from . import lifecycle
from .models import ChecklistItem, QAMeeting, RecurringTask, TaskInstance
from .serializers import (
    ChecklistItemSerializer, MeetingSerializer, OpClientDetailSerializer, OpClientSerializer, RecurringSerializer, TaskSerializer,
)

MSG_OP_ONLY = "Only Operation can do this."
MSG_HEAD_ONLY = "Only the Operation head can do this."
MSG_NOT_YOURS = "You can only handle tasks assigned to you."


class Base(viewsets.GenericViewSet):
    required_capabilities = {"*": ["operation.access"]}
    denied_message = "You don't have access to Operation."
    pagination_class = StandardPagination

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["today"] = sla_now()[0]
        return ctx

    def need_op(self):
        if not access.is_op(self.request.user):
            raise PermissionDenied(MSG_OP_ONLY)

    def need_head(self):
        if not access.is_op_head(self.request.user):
            raise PermissionDenied(MSG_HEAD_ONLY)

    def client_or_404(self, raw):
        client = Client.objects.filter(access.visible_clients_q(self.request.user), pk=int(raw) if str(raw or "").isdigit() else 0).first()
        if client is None:
            raise NotFound("Record not found.")
        return client


class OpClientViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, Base):
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["company_name", "contact_person", "email", "phone"]
    filterset_fields = ["status"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Client.objects.none()
        today = sla_now()[0]
        last = QAMeeting.objects.filter(client=OuterRef("pk")).order_by("-held_on", "-id")
        qs = (
            Client.objects.filter(access.visible_clients_q(self.request.user))
            .annotate(
                open_tasks=Count("tasks", filter=Q(tasks__status__in=TaskInstance.ACTIVE), distinct=True),
                overdue_tasks=Count("tasks", filter=Q(tasks__status__in=TaskInstance.ACTIVE, tasks__due_date__lt=today), distinct=True),
                required_total=Count("checklist", filter=Q(checklist__required=True, checklist__archived_at__isnull=True), distinct=True),
                required_done=Count(
                    "checklist", filter=Q(checklist__required=True, checklist__archived_at__isnull=True, checklist__status__in=["verified", "not_applicable"]), distinct=True
                ),
                last_next_qa=Subquery(last.values("next_date")[:1]),
                last_held=Subquery(last.values("held_on")[:1]),
            )
            .distinct()
            .order_by("company_name", "id")
        )
        if self.action == "retrieve":
            qs = qs.prefetch_related("checklist", "checklist__verified_by", "checklist__versions__uploaded_by", "checklist__versions__verified_by", "recurring_tasks", "recurring_tasks__assignee", "handovers", "projects")
        return qs

    def get_serializer_class(self):
        return OpClientDetailSerializer if self.action == "retrieve" else OpClientSerializer

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def out(self, client):
        client = self.get_queryset().prefetch_related("checklist", "checklist__verified_by", "checklist__versions__uploaded_by", "checklist__versions__verified_by", "recurring_tasks", "recurring_tasks__assignee", "handovers", "projects").get(pk=client.pk)
        return Response(OpClientDetailSerializer(client, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def cadence(self, request, pk=None):
        self.need_head()
        return self.out(services.set_cadence(request.user, self.get_object(), request.data.get("qa_cadence_days")))

    @action(detail=True, methods=["post"])
    def checklist(self, request, pk=None):
        self.need_head()
        client = self.get_object()
        services.add_item(request.user, client, request.data.get("name_en"), request.data.get("name_ar"), request.data.get("required", True))
        return self.out(client)


class ChecklistViewSet(Base):
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ChecklistItem.objects.none()
        return ChecklistItem.objects.filter(client__in=Client.objects.filter(access.visible_clients_q(self.request.user))).select_related("client", "verified_by")

    def item(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def respond(self, item):
        item = ChecklistItem.objects.select_related("verified_by").prefetch_related("versions__uploaded_by", "versions__verified_by").get(pk=item.pk)
        return Response(ChecklistItemSerializer(item).data)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        self.need_op()
        return self.respond(services.verify_item(request.user, self.item(), request.data.get("expires_on")))

    @action(detail=True, methods=["post"])
    def reset(self, request, pk=None):
        self.need_op()
        return self.respond(services.reset_item(request.user, self.item(), request.data.get("note")))

    @action(detail=True, methods=["post"], url_path="not-applicable")
    def not_applicable(self, request, pk=None):
        self.need_op()
        return self.respond(services.mark_not_applicable(request.user, self.item(), request.data.get("reason")))

    @action(detail=True, methods=["post"])
    def required(self, request, pk=None):
        self.need_head()
        return self.respond(services.set_required(request.user, self.item(), request.data.get("required")))

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        self.need_head()
        return self.respond(services.archive_item(request.user, self.item()))


class RecurringViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, Base):
    serializer_class = RecurringSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["client", "active"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return RecurringTask.objects.none()
        return RecurringTask.objects.filter(client__in=Client.objects.filter(access.visible_clients_q(self.request.user))).select_related("client", "assignee")

    def create(self, request, *args, **kwargs):
        self.need_head()
        client = self.client_or_404(request.data.get("client"))
        task = services.create_recurring(request.user, client, request.data)
        return Response(RecurringSerializer(task).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        self.need_head()
        task = services.update_recurring(request.user, self.get_object(), request.data)
        return Response(RecurringSerializer(task).data)


class TaskViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, Base):
    serializer_class = TaskSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["client", "status"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return TaskInstance.objects.none()
        qs = TaskInstance.objects.filter(client__in=Client.objects.filter(access.visible_clients_q(self.request.user))).select_related("client", "assignee", "closed_by").prefetch_related("escalations", "deliverables")
        p = self.request.query_params
        if p.get("mine") == "1":
            qs = qs.filter(assignee=self.request.user)
        if p.get("overdue") == "1":
            qs = qs.filter(status__in=TaskInstance.ACTIVE, due_date__lt=sla_now()[0])
        return qs

    def task(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def guard(self, task):
        self.need_op()
        if not access.can_work_task(self.request.user, task):
            raise PermissionDenied(MSG_NOT_YOURS)

    def respond(self, task):
        return Response(TaskSerializer(TaskInstance.objects.select_related("client", "assignee", "closed_by").get(pk=task.pk), context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Closes a task straight away, without a review. Only the Operation head may; everyone else submits it for review."""
        task = self.task()
        self.need_head()
        return self.respond(services.complete_task(request.user, task, request.data.get("note")))

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        return self.respond(lifecycle.start(request.user, self.task()))

    @action(detail=True, methods=["post"])
    def progress(self, request, pk=None):
        return self.respond(lifecycle.set_progress(request.user, self.task(), request.data.get("progress"), request.data.get("note")))

    @action(detail=True, methods=["post"])
    def wait(self, request, pk=None):
        return self.respond(lifecycle.wait(request.user, self.task(), request.data.get("reason")))

    @action(detail=True, methods=["post"])
    def block(self, request, pk=None):
        return self.respond(lifecycle.block(request.user, self.task(), request.data.get("reason")))

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        return self.respond(lifecycle.resume(request.user, self.task()))

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        return self.respond(lifecycle.submit(request.user, self.task(), request.data.get("note")))

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self.respond(lifecycle.approve(request.user, self.task()))

    @action(detail=True, methods=["post"], url_path="return")
    def send_back(self, request, pk=None):
        return self.respond(lifecycle.send_back(request.user, self.task(), request.data.get("comment")))

    @action(detail=True, methods=["post"])
    def escalate(self, request, pk=None):
        lifecycle.escalate(request.user, self.task(), request.data.get("reason"))
        return self.respond(self.task())

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        lifecycle.publish(request.user, self.task(), request.data.get("attachment"), request.data.get("title"))
        return self.respond(self.task())

    @action(detail=True, methods=["post"])
    def skip(self, request, pk=None):
        task = self.task()
        self.guard(task)
        return self.respond(services.skip_task(request.user, task, request.data.get("reason")))


class AssigneeViewSet(Base):
    """The people a task can be given to: active Operation staff. Visible to anyone who can open Operation."""

    def list(self, request):
        people = services.operation_users().order_by("full_name")
        return Response([{"id": u.pk, "full_name": u.full_name, "is_head": u.is_dept_head} for u in people])


class MeetingViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, Base):
    serializer_class = MeetingSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["client"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return QAMeeting.objects.none()
        return QAMeeting.objects.filter(client__in=Client.objects.filter(access.visible_clients_q(self.request.user))).select_related("logged_by")

    def create(self, request, *args, **kwargs):
        self.need_op()
        client = self.client_or_404(request.data.get("client"))

        def parse(key):
            raw = request.data.get(key)
            if not raw:
                return None
            try:
                return date.fromisoformat(str(raw))
            except ValueError:
                raise ValidationError({key: [services.MSG_HELD if key == "held_on" else services.MSG_NEXT]})

        m = services.log_meeting(request.user, client, parse("held_on"), request.data.get("notes"), parse("next_date"))
        return Response(MeetingSerializer(QAMeeting.objects.select_related("logged_by").get(pk=m.pk)).data, status=status.HTTP_201_CREATED)
