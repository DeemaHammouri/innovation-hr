from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.pagination import StandardPagination

from . import scope, services
from .models import GeneralTask


class GeneralTaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source="assignee.full_name", read_only=True)
    assignee_department = serializers.CharField(source="assignee.department.name", default=None, read_only=True)
    assigned_by_name = serializers.CharField(source="assigned_by.full_name", read_only=True)
    overdue = serializers.SerializerMethodField()
    can_done = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_attach = serializers.SerializerMethodField()

    class Meta:
        model = GeneralTask
        fields = [
            "id", "title", "description", "assignee", "assignee_name", "assignee_department", "assigned_by", "assigned_by_name", "deadline", "status",
            "done_at", "done_late", "overdue", "can_done", "can_edit", "can_attach", "created_at",
        ]
        read_only_fields = fields

    def _user(self):
        return self.context["request"].user

    def get_overdue(self, t):
        return t.status == GeneralTask.Status.OPEN and t.deadline < self.context["today"]

    def get_can_done(self, t):
        return t.status == GeneralTask.Status.OPEN and t.assignee_id == self._user().pk

    def get_can_edit(self, t):
        return t.status == GeneralTask.Status.OPEN and scope.can_manage(self._user(), t)

    def get_can_attach(self, t):
        return t.status == GeneralTask.Status.OPEN and (t.assignee_id == self._user().pk or scope.can_manage(self._user(), t))


def counts(qs, today):
    """One set of numbers for any list of tasks: the same words and the same sums everywhere they are shown."""
    open_q = Q(status="open")
    row = qs.aggregate(
        open=Count("id", filter=open_q), overdue=Count("id", filter=open_q & Q(deadline__lt=today)), due_today=Count("id", filter=open_q & Q(deadline=today)),
        done=Count("id", filter=Q(status="done")), done_late=Count("id", filter=Q(status="done", done_late=True)),
    )
    return {k: row[k] for k in ("open", "overdue", "due_today", "done", "done_late")}


class GeneralTaskViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    required_capabilities = {"*": ["gtask.access"]}
    denied_message = "You don't have access to tasks."
    serializer_class = GeneralTaskSerializer
    pagination_class = StandardPagination
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["today"] = timezone.localdate()
        return ctx

    def base(self):
        return GeneralTask.objects.select_related("assignee", "assignee__department", "assigned_by")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return GeneralTask.objects.none()
        user, p = self.request.user, self.request.query_params
        qs = self.base().filter(scope.visible_q(user))
        if self.action != "list":
            return qs  # one task by its id: the filters below only shape the list
        view = p.get("view", "mine")
        if view == "mine":
            qs = qs.filter(assignee=user)
        elif view == "given":
            qs = qs.filter(assigned_by=user)
        today = timezone.localdate()
        if p.get("status") in ("open", "done"):
            qs = qs.filter(status=p["status"])
        if p.get("overdue") == "1":
            qs = qs.filter(status="open", deadline__lt=today)
        if str(p.get("assignee", "")).isdigit():
            qs = qs.filter(assignee_id=int(p["assignee"]))
        return qs

    def create(self, request, *args, **kwargs):
        task = services.create(request.user, request.data)
        return Response(self.get_serializer(self.base().get(pk=task.pk)).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        task = services.update(request.user, self.get_object(), request.data)
        return Response(self.get_serializer(self.base().get(pk=task.pk)).data)

    @action(detail=True, methods=["post"])
    def done(self, request, pk=None):
        task = services.mark_done(request.user, self.get_object())
        return Response(self.get_serializer(self.base().get(pk=task.pk)).data)

    @action(detail=False, methods=["get"])
    def counters(self, request):
        """`mine` for everyone; `team` (everything this person may see) for the CEO and department heads."""
        today = timezone.localdate()
        user = request.user
        out = {"mine": counts(GeneralTask.objects.filter(assignee=user), today), "team": None}
        if user.has_capability("gtask.assign_any") or user.has_capability("gtask.assign_team"):
            out["team"] = counts(GeneralTask.objects.filter(scope.visible_q(user)), today)
        return Response(out)

    @action(detail=False, methods=["get"])
    def assignees(self, request):
        """Who this person may give a task to."""
        rows = scope.assignable_users(request.user).select_related("department")
        return Response([{"id": u.pk, "full_name": u.full_name, "department": u.department.name if u.department_id else None} for u in rows])
