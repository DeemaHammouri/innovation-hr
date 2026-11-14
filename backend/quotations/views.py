from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from accounts.permissions import PasswordChangeNotPending
from core.pagination import StandardPagination
from leads.models import Lead
from leads.sla import sla_now

from . import access, services
from .filters import QuotationFilter
from .models import Quotation, QuotationVersion
from .serializers import QuotationDetailSerializer, QuotationSerializer

MSG_NO_REQUEST = "You can't request a quotation for this lead."
MSG_HR_ONLY = "Only HR can prepare quotations."
MSG_HEAD_ONLY = "Only the Commercial head can do this."
MSG_NO_PIPELINE = "Only the Commercial head or the assigned member can do this."


class HasQuotationAccess(BasePermission):
    message = "You don't have access to quotations."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and access.has_access(request.user))


class QuotationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [HasQuotationAccess, PasswordChangeNotPending]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = QuotationFilter
    search_fields = ["ref", "lead__company_name", "lead__ref", "lead__contact_name"]
    ordering_fields = ["created_at", "status", "next_follow_up"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        return (
            Quotation.objects.filter(access.visible_q(self.request.user))
            .select_related("lead", "lead__assigned_to", "requested_by", "prepared_by", "signed_by", "rejection_reason")
            .prefetch_related(Prefetch("versions", queryset=QuotationVersion.objects.order_by("number")))
        )

    def get_serializer_class(self):
        return QuotationDetailSerializer if self.action != "list" else QuotationSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["today"] = sla_now()[0]
        return ctx

    def get_object(self):
        qs = self.get_queryset()
        if self.action == "retrieve":
            qs = qs.prefetch_related("versions__lines", "versions__created_by")
        return get_object_or_404(qs, pk=self.kwargs["pk"])

    def out(self, q, code=status.HTTP_200_OK):
        q = (
            Quotation.objects.select_related("lead", "lead__assigned_to", "requested_by", "prepared_by", "signed_by", "rejection_reason")
            .prefetch_related("versions__lines", "versions__created_by").get(pk=q.pk)
        )
        return Response(QuotationDetailSerializer(q, context=self.get_serializer_context()).data, status=code)

    def create(self, request, *args, **kwargs):
        raw = request.data.get("lead")
        lead = Lead.objects.filter(access.lead_access.visible_q(request.user), pk=int(raw) if str(raw or "").isdigit() else 0).first()
        if lead is None:
            raise NotFound("Record not found.")
        if not access.acts_on_lead(request.user, lead):
            raise PermissionDenied(MSG_NO_REQUEST)
        # The service says what is wrong when the lead is not ready (not qualified, skipped, already has one).
        return self.out(services.request_quotation(request.user, lead, request.data.get("note")), status.HTTP_201_CREATED)

    # ---- HR: prepare ----
    def _hr(self, request):
        if not access.is_hr(request.user):
            raise PermissionDenied(MSG_HR_ONLY)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        self._hr(request)
        return self.out(services.start_preparing(request.user, self.get_object()))

    @action(detail=True, methods=["put"])
    def draft(self, request, pk=None):
        self._hr(request)
        return self.out(services.save_draft(request.user, self.get_object(), request.data))

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        self._hr(request)
        return self.out(services.submit(request.user, self.get_object()))

    # ---- Commercial head: review ----
    def _head(self, request):
        if not access.is_head(request.user):
            raise PermissionDenied(MSG_HEAD_ONLY)

    @action(detail=True, methods=["post"], url_path="request-changes")
    def request_changes(self, request, pk=None):
        self._head(request)
        return self.out(services.request_changes(request.user, self.get_object(), request.data.get("comment")))

    @action(detail=True, methods=["post"])
    def sign(self, request, pk=None):
        self._head(request)
        return self.out(services.sign(request.user, self.get_object()))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        self._head(request)
        return self.out(services.cancel(request.user, self.get_object(), request.data.get("reason")))

    # ---- Commercial pipeline: send and record the outcome ----
    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        q = self.get_object()
        if not access.on_pipeline(request.user, q):
            raise PermissionDenied(MSG_NO_PIPELINE)
        return self.out(services.mark_sent(request.user, q))

    @action(detail=True, methods=["post"])
    def outcome(self, request, pk=None):
        q = self.get_object()
        if not access.on_pipeline(request.user, q):
            raise PermissionDenied(MSG_NO_PIPELINE)
        follow = request.data.get("next_follow_up")
        parsed = None
        if follow:
            from datetime import date
            try:
                parsed = date.fromisoformat(str(follow))
            except ValueError:
                raise ValidationError({"next_follow_up": [services.MSG_FOLLOW_UP]})
        reason = request.data.get("rejection_reason")
        return self.out(services.set_outcome(
            request.user, q, outcome=request.data.get("outcome", ""), next_follow_up=parsed,
            reason_id=int(reason) if str(reason or "").isdigit() else None, note=request.data.get("rejection_note", ""),
        ))
