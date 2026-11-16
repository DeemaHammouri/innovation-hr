"""The Operation monitoring view: who has how much on their plate, what is late, stuck, escalated or waiting for a review.
Read-only, for the Operation head and the CEO. It carries task titles and client names, no money."""
from django.db.models import Count, Q
from rest_framework.response import Response
from rest_framework.views import APIView

from leads.sla import sla_now

from .models import Escalation, TaskInstance

CAP = 50


class MonitoringView(APIView):
    required_capabilities = ["operation.monitor"]
    denied_message = "Only the Operation head and the CEO can open the monitoring view."

    def get(self, request):
        today = sla_now()[0]
        late = Q(status__in=TaskInstance.ACTIVE, due_date__lt=today)
        per_person = (
            TaskInstance.objects.filter(assignee__isnull=False)
            .values("assignee", "assignee__full_name")
            .annotate(
                open=Count("id", filter=Q(status="open")), in_progress=Count("id", filter=Q(status="in_progress")), waiting=Count("id", filter=Q(status="waiting")),
                blocked=Count("id", filter=Q(status="blocked")), submitted=Count("id", filter=Q(status="submitted")), overdue=Count("id", filter=late),
            )
            .order_by("assignee__full_name")
        )
        totals = TaskInstance.objects.aggregate(
            open=Count("id", filter=Q(status="open")), in_progress=Count("id", filter=Q(status="in_progress")), waiting=Count("id", filter=Q(status="waiting")),
            blocked=Count("id", filter=Q(status="blocked")), submitted=Count("id", filter=Q(status="submitted")), overdue=Count("id", filter=late),
            unassigned=Count("id", filter=Q(status__in=TaskInstance.ACTIVE, assignee__isnull=True)),
        )
        attention = TaskInstance.objects.filter(late | Q(status__in=["blocked", "submitted"]) | Q(escalations__isnull=False)).distinct().select_related("client", "assignee").prefetch_related("escalations").order_by("due_date")[:CAP]
        return Response({
            "today": today.isoformat(),
            "totals": totals,
            "people": [{"id": r["assignee"], "name": r["assignee__full_name"], **{k: r[k] for k in ("open", "in_progress", "waiting", "blocked", "submitted", "overdue")}} for r in per_person],
            "attention": [
                {
                    "id": t.pk, "title": t.title, "client": t.client_id, "client_name": t.client.company_name, "assignee_name": t.assignee.full_name if t.assignee else None,
                    "status": t.status, "due_date": t.due_date, "overdue": t.status in TaskInstance.ACTIVE and t.due_date < today,
                    "escalation_level": max((e.level for e in t.escalations.all()), default=0),
                }
                for t in attention
            ],
            "escalations_open": Escalation.objects.filter(task__status__in=[*TaskInstance.ACTIVE, "submitted"]).count(),
        })
