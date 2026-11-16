"""Process tracking for the administration: what moved today, what is late, who did what. Read-only, built from the records and the
append-only history, so it can never disagree with them. Needs the `tracking.view` capability."""
from datetime import datetime, time, timedelta

from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from core.pagination import StandardPagination

from .models import AuditEntry

KINDS = {"lead": "lead", "quotation": "quotation", "contract": "contract", "appointment": "appointment", "client": "client", "meetingreport": "meeting report"}
ITEM_CAP = 50


def start_of_today():
    return timezone.make_aware(datetime.combine(timezone.localdate(), time.min))


def _minutes(name):
    return int(getattr(settings, name, 60))


def _kind(entry):
    return KINDS.get(entry.content_type.model, entry.content_type.model)


class FeedSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", default=None, read_only=True)
    kind = serializers.SerializerMethodField()

    class Meta:
        model = AuditEntry
        fields = ["id", "actor", "actor_name", "kind", "object_id", "action", "from_value", "to_value", "comment", "created_at"]
        read_only_fields = fields

    def get_kind(self, e):
        return _kind(e)


class TrackingView(APIView):
    required_capabilities = {"get": ["tracking.view"]}
    denied_message = "Only the administration can see process tracking."

    def get(self, request):
        from appointments.models import Appointment
        from clients.models import Client
        from leads.models import Lead
        from quotations.models import Quotation

        now = timezone.now()
        today = start_of_today()
        hr_limit, com_limit, appt_limit = (timedelta(minutes=_minutes(n)) for n in ("URGENT_HR_MINUTES", "URGENT_COMMERCIAL_MINUTES", "URGENT_APPOINTMENT_MINUTES"))

        changes = AuditEntry.objects.filter(created_at__gte=today).exclude(action__in=("comment",)).select_related("actor", "content_type").order_by("-created_at")
        changed_today = [FeedSerializer(e).data for e in changes[:ITEM_CAP]]

        late_quotations = []
        from notifications.urgent import quotation_assignments

        for q, since in quotation_assignments():
            if now - since >= hr_limit:
                late_quotations.append({"id": q.pk, "ref": q.ref, "company": q.lead.company_name, "stage": "preparation", "person": q.assigned_to.full_name, "since": since, "minutes_late": int((now - since - hr_limit).total_seconds() // 60)})
        for q in Quotation.objects.filter(status="in_review").select_related("lead").prefetch_related("versions"):
            v = max(q.versions.all(), key=lambda v: v.number, default=None)
            if v and v.submitted_at and now - v.submitted_at >= com_limit:
                late_quotations.append({"id": q.pk, "ref": q.ref, "company": q.lead.company_name, "stage": "signature", "person": None, "since": v.submitted_at, "minutes_late": int((now - v.submitted_at - com_limit).total_seconds() // 60)})

        missed = [
            {"id": a.pk, "title": a.title, "owner": a.owner.full_name, "starts_at": a.starts_at, "lead": a.lead.company_name if a.lead_id else None}
            for a in Appointment.objects.filter(status="scheduled", starts_at__lte=now - appt_limit).select_related("owner", "lead").order_by("starts_at")[:ITEM_CAP]
        ]
        overdue = [
            {"id": l.pk, "ref": l.ref, "company": l.company_name, "due": l.next_follow_up, "owner": l.assigned_to.full_name if l.assigned_to_id else None}
            for l in Lead.objects.filter(status="waiting", archived_at__isnull=True, next_follow_up__lt=timezone.localdate()).select_related("assigned_to").order_by("next_follow_up")[:ITEM_CAP]
        ]
        pipeline = {
            "leads": {r["status"]: r["n"] for r in Lead.objects.filter(archived_at__isnull=True).values("status").annotate(n=Count("id"))},
            "clients": {(r["decision"] or "undecided"): r["n"] for r in Client.objects.values("decision").annotate(n=Count("id"))},
        }
        week = now - timedelta(days=7)
        team = [
            {"id": r["actor"], "name": r["actor__full_name"], "today": 0, "week": r["week"]}
            for r in AuditEntry.objects.filter(created_at__gte=week, actor__isnull=False).values("actor", "actor__full_name").annotate(week=Count("id"))
            .order_by("-week")[:ITEM_CAP]
        ]
        today_counts = dict(AuditEntry.objects.filter(created_at__gte=today, actor__isnull=False).values_list("actor").annotate(n=Count("id")))
        for row in team:
            row["today"] = today_counts.get(row["id"], 0)
        return Response({
            "generated_at": now, "thresholds": {"hr": _minutes("URGENT_HR_MINUTES"), "commercial": _minutes("URGENT_COMMERCIAL_MINUTES"), "appointment": _minutes("URGENT_APPOINTMENT_MINUTES")},
            "changed_today": changed_today, "late_quotations": late_quotations, "missed_appointments": missed, "overdue_follow_ups": overdue, "pipeline": pipeline, "team": team,
        })


class FeedView(ListAPIView):
    """GET /api/admin/activity/?actor=<user id>&action=<key>&kind=<record kind>&from=&to= : the whole activity feed."""

    required_capabilities = {"get": ["tracking.view"]}
    denied_message = "Only the administration can see the activity feed."
    serializer_class = FeedSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        from django.utils.dateparse import parse_date

        qs = AuditEntry.objects.select_related("actor", "content_type")
        p = self.request.query_params
        if p.get("actor", "").isdigit():
            qs = qs.filter(actor_id=int(p["actor"]))
        if p.get("action"):
            qs = qs.filter(action=p["action"][:60])
        if p.get("kind") in KINDS:
            qs = qs.filter(content_type__model=p["kind"])
        start, end = parse_date(p.get("from", "")), parse_date(p.get("to", ""))
        if start:
            qs = qs.filter(created_at__gte=timezone.make_aware(datetime.combine(start, time.min)))
        if end:
            qs = qs.filter(created_at__lt=timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min)))
        return qs.order_by("-created_at", "-id")


class FeedFiltersView(APIView):
    """What the feed's filters offer: the people who have acted and the action keys that exist."""

    required_capabilities = {"get": ["tracking.view"]}
    denied_message = "Only the administration can see the activity feed."

    def get(self, request):
        people = User.objects.filter(pk__in=AuditEntry.objects.exclude(actor=None).values("actor")).order_by("full_name")
        return Response({
            "people": [{"id": u.pk, "name": u.full_name} for u in people],
            "actions": sorted(AuditEntry.objects.values_list("action", flat=True).distinct()),
            "kinds": [{"key": k, "label": v} for k, v in KINDS.items()],
        })
