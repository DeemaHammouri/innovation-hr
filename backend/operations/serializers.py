from datetime import timedelta

from rest_framework import serializers

from clients.models import Client

from . import access
from .models import ChecklistItem, QAMeeting, RecurringTask, TaskInstance


class ChecklistItemSerializer(serializers.ModelSerializer):
    verified_by_name = serializers.CharField(source="verified_by.full_name", default=None, read_only=True)
    versions = serializers.SerializerMethodField()

    class Meta:
        model = ChecklistItem
        fields = [
            "id", "client", "name_en", "name_ar", "required", "status", "na_reason", "verified_by_name", "verified_at", "position", "expires_required", "expires_on",
            "versions",
        ]
        read_only_fields = fields

    def get_versions(self, i):
        return [
            {
                "number": v.number, "filename": v.filename, "state": v.state, "uploaded_by_name": v.uploaded_by.full_name if v.uploaded_by else None,
                "uploaded_at": v.uploaded_at, "verified_by_name": v.verified_by.full_name if v.verified_by else None, "verified_at": v.verified_at,
                "expires_on": v.expires_on, "attachment": v.attachment_id,
            }
            for v in i.versions.all()
        ]


class RecurringSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source="assignee.full_name", default=None, read_only=True)
    client_name = serializers.CharField(source="client.company_name", read_only=True)

    class Meta:
        model = RecurringTask
        fields = ["id", "client", "client_name", "title", "description", "frequency", "interval_days", "start_date", "next_due", "assignee", "assignee_name", "active"]
        read_only_fields = fields


class TaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(source="assignee.full_name", default=None, read_only=True)
    client_name = serializers.CharField(source="client.company_name", read_only=True)
    closed_by_name = serializers.CharField(source="closed_by.full_name", default=None, read_only=True)
    overdue = serializers.SerializerMethodField()
    can_work = serializers.SerializerMethodField()
    can_publish = serializers.SerializerMethodField()
    escalation_level = serializers.SerializerMethodField()
    can_review = serializers.SerializerMethodField()
    can_escalate = serializers.SerializerMethodField()
    can_complete = serializers.SerializerMethodField()
    deliverables = serializers.SerializerMethodField()

    class Meta:
        model = TaskInstance
        fields = [
            "id", "client", "client_name", "recurring", "title", "due_date", "assignee", "assignee_name", "status", "completion_note", "skip_reason",
            "closed_by_name", "closed_at", "overdue", "can_work", "progress", "started_at", "status_reason", "submitted_at", "review_note", "escalation_level",
            "can_review", "can_escalate", "can_complete", "can_publish", "deliverables",
        ]
        read_only_fields = fields

    def get_overdue(self, t):
        today = self.context.get("today")
        return bool(t.status in TaskInstance.ACTIVE and today and t.due_date < today)

    def get_can_work(self, t):
        return t.status in TaskInstance.ACTIVE and access.can_work_task(self.context["request"].user, t)

    def get_can_publish(self, t):
        """Matches lifecycle.publish: after submitting, the assignee (who can no longer 'work') and the reviewers may show a file to the client."""
        u = self.context["request"].user
        return t.status in ("submitted", "done") and (u.has_capability("operation.review") or access.can_work_task(u, t))

    def get_escalation_level(self, t):
        return max((e.level for e in t.escalations.all()), default=0)

    def get_can_review(self, t):
        u = self.context["request"].user
        return t.status == "submitted" and u.has_capability("operation.review") and t.assignee_id != u.pk

    def get_can_escalate(self, t):
        return (t.status in TaskInstance.ACTIVE or t.status == "submitted") and access.can_work_task(self.context["request"].user, t) and self.get_escalation_level(t) < 2

    def get_can_complete(self, t):
        return t.status in TaskInstance.ACTIVE and self.context["request"].user.has_capability("operation.manage")

    def get_deliverables(self, t):
        return [{"id": d.pk, "title": d.title, "published_at": d.published_at, "acknowledged_at": d.acknowledged_at} for d in t.deliverables.all()]


class MeetingSerializer(serializers.ModelSerializer):
    logged_by_name = serializers.CharField(source="logged_by.full_name", read_only=True)

    class Meta:
        model = QAMeeting
        fields = ["id", "client", "held_on", "notes", "next_date", "logged_by_name", "created_at"]
        read_only_fields = fields


class OpClientSerializer(serializers.ModelSerializer):
    """List rows. The counts come from annotations on the queryset, so a page costs a fixed number of queries."""

    open_tasks = serializers.IntegerField(read_only=True, default=0)
    overdue_tasks = serializers.IntegerField(read_only=True, default=0)
    required_total = serializers.IntegerField(read_only=True, default=0)
    required_done = serializers.IntegerField(read_only=True, default=0)
    next_qa_due = serializers.SerializerMethodField()
    qa_overdue = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            "id", "company_name", "contact_person", "phone", "email", "status", "activated_at", "qa_cadence_days", "open_tasks", "overdue_tasks",
            "required_total", "required_done", "next_qa_due", "qa_overdue", "permissions",
        ]
        read_only_fields = fields

    def _next(self, c):
        explicit = getattr(c, "last_next_qa", None)
        if explicit:
            return explicit
        if getattr(c, "last_held", None):
            return c.last_held + timedelta(days=c.qa_cadence_days)
        base = (c.activated_at or c.created_at).date()
        return base + timedelta(days=c.qa_cadence_days) if c.status != "inactive" else None

    def get_next_qa_due(self, c):
        return self._next(c)

    def get_qa_overdue(self, c):
        nxt, today = self._next(c), self.context.get("today")
        return bool(nxt and today and nxt < today and c.status == "active")

    def get_permissions(self, c):
        return access.client_flags(self.context["request"].user, c)


class OpClientDetailSerializer(OpClientSerializer):
    address = serializers.CharField(read_only=True)
    checklist = serializers.SerializerMethodField()
    recurring_tasks = serializers.SerializerMethodField()
    handovers = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField()

    class Meta(OpClientSerializer.Meta):
        fields = OpClientSerializer.Meta.fields + ["address", "checklist", "recurring_tasks", "handovers", "projects"]
        read_only_fields = fields

    def get_checklist(self, c):
        items = [i for i in c.checklist.all() if i.archived_at is None]
        return ChecklistItemSerializer(items, many=True).data

    def get_recurring_tasks(self, c):
        return RecurringSerializer(list(c.recurring_tasks.all()), many=True).data

    def get_handovers(self, c):
        return [{"id": h.pk, "ref": h.ref, "status": h.status} for h in c.handovers.all() if h.status != "draft" or self.context["request"].user.has_capability("handover.write")]

    def get_projects(self, c):
        return [{"id": p.pk, "ref": p.ref, "status": p.status} for p in c.projects.all()]
