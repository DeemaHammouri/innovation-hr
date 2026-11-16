from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from core.concurrency import check_fresh
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from accounts.models import User
from core.pagination import StandardPagination

from . import access, importer, services
from .filters import LeadFilter, LeadSearch
from .models import ImportBatch, Lead
from .serializers import ContactInputSerializer, ImportBatchSerializer, InteractionSerializer, LeadSerializer
from .sla import sla_now

MSG_MARKETING_ONLY = "Only Marketing can add or import leads."
MSG_HEAD_ONLY = "Only the Commercial head can do this."
MSG_NO_EDIT = "You can't change this lead."
MSG_NO_LOG = "You can't log contacts on this lead."
MSG_NO_ARCHIVE = "You can't archive this lead."
MSG_NO_UNDO = "Only the person who imported this batch can undo it."

BOARD = ["new", "contacted", "waiting", "qualified", "rejected"]
BOARD_LIMIT = 50


def require_marketing(user):
    if not user.has_capability("lead.create"):
        raise PermissionDenied(MSG_MARKETING_ONLY)


def require_head(user):
    if not user.has_capability("lead.manage"):
        raise PermissionDenied(MSG_HEAD_ONLY)


class LeadViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    # Every action needs to be allowed into leads; the ones that are for one job also name its capability.
    required_capabilities = {
        "list": ["lead.access"], "retrieve": ["lead.access"], "board": ["lead.access"], "interactions": ["lead.access"],
        "outcome": ["lead.access"], "skip_quotation": ["lead.access"], "archive": ["lead.access"], "partial_update": ["lead.access"],
        "create": ["lead.access", "lead.create"],
        "assignees": ["lead.access", "lead.manage"], "assign": ["lead.access", "lead.manage"],
        "reopen": ["lead.access", "lead.manage"], "restore": ["lead.access", "lead.manage"],
        "import_template": ["lead.access", "lead.import"], "import_preview": ["lead.access", "lead.import"], "import_confirm": ["lead.access", "lead.import"],
    }
    denied_message = {
        "*": "You don't have access to leads.", "create": MSG_MARKETING_ONLY,
        "assignees": MSG_HEAD_ONLY, "assign": MSG_HEAD_ONLY, "reopen": MSG_HEAD_ONLY, "restore": MSG_HEAD_ONLY,
        "import_template": MSG_MARKETING_ONLY, "import_preview": MSG_MARKETING_ONLY, "import_confirm": MSG_MARKETING_ONLY,
    }
    serializer_class = LeadSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, LeadSearch, OrderingFilter]
    filterset_class = LeadFilter
    search_fields = ["ref", "company_name", "contact_name", "position", "phone", "email", "location"]
    ordering_fields = ["created_at", "updated_at", "next_follow_up", "company_name", "contact_name", "status", "ref"]
    ordering = ["-created_at", "-id"]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        return (
            Lead.objects.filter(access.visible_q(self.request.user))
            .select_related("assigned_to", "created_by", "batch", "rejection_reason")
            .prefetch_related("quotations", "contracts")
        )

    def get_object(self):
        # Not the list filters: an archived lead must still open. Visibility is already in get_queryset (hidden = 404).
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["today"], ctx["now"], ctx["sla"] = sla_now()
        return ctx

    def out(self, lead, code=status.HTTP_200_OK):
        lead = self.get_queryset().get(pk=lead.pk)
        return Response(self.get_serializer(lead).data, status=code)

    # ---- create and edit ----
    def create(self, request, *args, **kwargs):
        require_marketing(request.user)
        lead = services.create_lead(request.user, request.data, allow_duplicate=request.data.get("allow_duplicate") in (True, "true", "1", 1))
        return self.out(lead, status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        lead = self.get_object()
        if not access.can_edit(request.user, lead):
            raise PermissionDenied(MSG_NO_EDIT)
        check_fresh(lead, request.data)
        return self.out(services.update_lead(request.user, lead, request.data))

    # ---- the board: every stage with its count and its first cards ----
    @action(detail=False, methods=["get"])
    def board(self, request):
        qs = self.filter_queryset(self.get_queryset()).order_by("next_follow_up", "-updated_at")
        columns = []
        for st in BOARD:
            col = qs.filter(status=st)
            columns.append({"status": st, "count": col.count(), "results": self.get_serializer(col[:BOARD_LIMIT], many=True).data})
        return Response({"columns": columns, "limit": BOARD_LIMIT})

    # ---- people the head can assign to ----
    @action(detail=False, methods=["get"])
    def assignees(self, request):
        require_head(request.user)
        people = (
            User.objects.filter(is_active=True, department__name="Commercial")
            .annotate(open_leads=Count("leads_assigned", filter=Q(leads_assigned__status__in=["new", "contacted", "waiting"], leads_assigned__archived_at__isnull=True)))
            .order_by("full_name")
        )
        return Response([{"id": u.pk, "full_name": u.full_name, "role": u.role, "open_leads": u.open_leads} for u in people])

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        require_head(request.user)
        lead = self.get_object()
        assignee = User.objects.filter(pk=request.data.get("assigned_to")).select_related("department").first() if str(request.data.get("assigned_to") or "").isdigit() else None
        return self.out(services.assign(request.user, lead, assignee))

    # ---- contacts, outcomes, reopening ----
    @action(detail=True, methods=["get", "post"])
    def interactions(self, request, pk=None):
        lead = self.get_object()
        if request.method == "GET":
            rows = lead.interactions.select_related("created_by")
            return Response(InteractionSerializer(rows, many=True).data)
        if not access.can_pipeline_write(request.user, lead):
            raise PermissionDenied(MSG_NO_LOG)
        body = ContactInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        d = body.validated_data
        lead, _ = services.log_interaction(
            request.user, lead, type=d.get("type") or "call", occurred_at=d.get("occurred_at"), notes=d.get("notes", ""),
            outcome=d.get("outcome", ""), next_follow_up=d.get("next_follow_up"), reason_id=d.get("rejection_reason"), note=d.get("rejection_note", ""),
        )
        return self.out(lead, status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def outcome(self, request, pk=None):
        lead = self.get_object()
        if not access.can_pipeline_write(request.user, lead):
            raise PermissionDenied(MSG_NO_LOG)
        body = ContactInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        d = body.validated_data
        lead = services.set_outcome(
            request.user, lead, outcome=d.get("outcome", ""), next_follow_up=d.get("next_follow_up"),
            reason_id=d.get("rejection_reason"), note=d.get("rejection_note", ""),
        )
        return self.out(lead)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        require_head(request.user)
        return self.out(services.reopen(request.user, self.get_object(), request.data.get("note")))

    # ---- after Qualified: skip the quotation ----
    @action(detail=True, methods=["post"], url_path="skip-quotation")
    def skip_quotation(self, request, pk=None):
        lead = self.get_object()
        if not access.can_pipeline_write(request.user, lead):
            raise PermissionDenied(MSG_NO_LOG)
        return self.out(services.skip_quotation(request.user, lead, request.data.get("note")))

    # ---- archive instead of delete ----
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        lead = self.get_object()
        if not access.can_archive(request.user, lead):
            raise PermissionDenied(MSG_NO_ARCHIVE)
        return self.out(services.archive(request.user, lead, request.data.get("reason")))

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        require_head(request.user)
        return self.out(services.restore(request.user, self.get_object()))

    # ---- Excel / CSV import ----
    @action(detail=False, methods=["get"], url_path="import/template")
    def import_template(self, request):
        """?format=xlsx (default) or csv, ?lang=en or ar."""
        require_marketing(request.user)
        lang = "ar" if request.query_params.get("lang") == "ar" else "en"
        if request.query_params.get("file", "xlsx") == "csv":
            res = HttpResponse(importer.template_csv(lang), content_type="text/csv; charset=utf-8")
            res["Content-Disposition"] = f'attachment; filename="leads-template-{lang}.csv"'
            return res
        res = HttpResponse(importer.template_xlsx(lang), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        res["Content-Disposition"] = f'attachment; filename="leads-template-{lang}.xlsx"'
        return res

    @action(detail=False, methods=["post"], url_path="import/preview")
    def import_preview(self, request):
        require_marketing(request.user)
        return Response(importer.parse(request.FILES.get("file")))

    @action(detail=False, methods=["post"], url_path="import/confirm")
    def import_confirm(self, request):
        require_marketing(request.user)
        batch = importer.confirm(request.user, request.FILES.get("file"))
        return Response(ImportBatchSerializer(batch, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ImportBatchViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Marketing sees their own batches. The Commercial head and the CEO can read them all."""

    required_capabilities = {"list": ["lead.batches"], "retrieve": ["lead.batches"], "undo": ["lead.batches"]}
    denied_message = "You don't have access to import batches."
    serializer_class = ImportBatchSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = ImportBatch.objects.select_related("created_by").annotate(contacted_n=Count("leads", filter=~Q(leads__status="new")))
        if not self.request.user.has_capability("lead.batches_all"):
            qs = qs.filter(created_by=self.request.user)
        return qs

    @action(detail=True, methods=["post"])
    def undo(self, request, pk=None):
        batch = self.get_object()
        if batch.created_by_id != request.user.pk:
            raise PermissionDenied(MSG_NO_UNDO)
        batch = importer.undo(request.user, batch)
        batch = self.get_queryset().get(pk=batch.pk)
        return Response(self.get_serializer(batch).data)
