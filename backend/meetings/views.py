from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from appointments.models import Appointment
from appointments.services import can_manage
from core.pagination import StandardPagination
from documents import builders as doc_builders
from documents import serve as doc_serve

from . import access, services
from .models import MeetingReport

RELATED = ("lead", "appointment", "author", "signed_by", "ceo_by")


class ReportSerializer(serializers.ModelSerializer):
    ref = serializers.SerializerMethodField()
    lead_company = serializers.CharField(source="lead.company_name", read_only=True)
    appointment_title = serializers.CharField(source="appointment.title", read_only=True)
    author_name = serializers.CharField(source="author.full_name", read_only=True)
    signed_by_name = serializers.CharField(source="signed_by.full_name", default=None, read_only=True)
    ceo_by_name = serializers.CharField(source="ceo_by.full_name", default=None, read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = MeetingReport
        fields = [
            "id", "ref", "appointment", "appointment_title", "lead", "lead_company", "status", "author_name", "held_on", "attendees", "summary", "decisions",
            "next_steps", "signed_by_name", "signed_at", "ceo_by_name", "ceo_at", "ceo_comment", "created_at", "updated_at", "permissions",
        ]
        read_only_fields = fields

    def get_ref(self, r):
        return services.ref(r)

    def get_permissions(self, r):
        return access.flags(self.context["request"].user, r)


class MeetingReportViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    required_capabilities = {
        "*": ["meeting_report.write"], "list": [], "retrieve": [], "document": [],
        "sign": ["meeting_report.sign"], "approve": ["meeting_report.approve"], "return_": ["meeting_report.approve"],
    }
    denied_message = {
        "*": "You can't work on meeting reports.", "sign": "Only the Commercial head can sign a report.",
        "approve": "Only the CEO can approve a report.", "return_": "Only the CEO can approve a report.",
    }
    serializer_class = ReportSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = MeetingReport.objects.filter(access.visible_q(self.request.user)).select_related(*RELATED)
        p = self.request.query_params
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("appointment", "").isdigit():
            qs = qs.filter(appointment_id=int(p["appointment"]))
        if p.get("lead", "").isdigit():
            qs = qs.filter(lead_id=int(p["lead"]))
        return qs.order_by("-held_on", "-id")

    def out(self, r, code=200):
        return Response(self.get_serializer(MeetingReport.objects.select_related(*RELATED).get(pk=r.pk)).data, status=code)

    def create(self, request, *args, **kwargs):
        raw = request.data.get("appointment")
        appt = Appointment.objects.select_related("lead", "owner", "created_by").filter(pk=int(raw) if str(raw or "").isdigit() else 0).first()
        if appt is None or not (can_manage(request.user, appt) or request.user.has_capability("meeting_report.view_all")):
            raise NotFound("Record not found.")
        return self.out(services.create(request.user, appt, request.data), 201)

    def partial_update(self, request, *args, **kwargs):
        return self.out(services.update(request.user, self.get_object(), request.data))

    @action(detail=True, methods=["post"])
    def sign(self, request, pk=None):
        return self.out(services.sign(request.user, self.get_object(), request.data.get("signature")))

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self.out(services.approve(request.user, self.get_object()))

    @action(detail=True, methods=["post"], url_path="return")
    def return_(self, request, pk=None):
        return self.out(services.return_(request.user, self.get_object(), request.data.get("comment")))

    @action(detail=True, methods=["get"])
    def document(self, request, pk=None):
        r = self.get_object()
        fmt, lang = doc_serve.options(request)
        return doc_serve.respond(doc_builders.build_meeting_report(r), fmt, lang)
