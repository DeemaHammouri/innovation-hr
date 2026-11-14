from datetime import date

from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from accounts.permissions import PasswordChangeNotPending
from core.pagination import StandardPagination
from leads import access as lead_access
from leads.models import Lead

from . import access, services
from .filters import ContractFilter
from .models import Contract
from .serializers import ContractDetailSerializer, ContractSerializer

MSG_NO_REQUEST = "You can't request a contract for this lead."
MSG_HR_ONLY = "Only HR can prepare contracts."
MSG_HEAD_ONLY = "Only the Commercial head can do this."
MSG_CEO_ONLY = "Only the CEO can do this."
MSG_NO_PIPELINE = "Only the Commercial head or the assigned member can do this."

RELATED = ("lead", "lead__assigned_to", "quotation", "requested_by", "drafted_by", "meeting_by", "signed_by", "handed_over_by")


class HasContractAccess(BasePermission):
    message = "You don't have access to contracts."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and access.has_access(request.user))


class ContractViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [HasContractAccess, PasswordChangeNotPending]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ContractFilter
    search_fields = ["ref", "lead__company_name", "lead__ref", "lead__contact_name"]
    ordering_fields = ["created_at", "status"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        return Contract.objects.filter(access.visible_q(self.request.user)).select_related(*RELATED)

    def get_serializer_class(self):
        return ContractDetailSerializer if self.action != "list" else ContractSerializer

    def get_object(self):
        qs = self.get_queryset()
        if self.action == "retrieve":
            qs = qs.prefetch_related("versions__created_by")
        return get_object_or_404(qs, pk=self.kwargs["pk"])

    def out(self, c, code=status.HTTP_200_OK):
        c = Contract.objects.select_related(*RELATED).prefetch_related("versions__created_by").get(pk=c.pk)
        return Response(ContractDetailSerializer(c, context=self.get_serializer_context()).data, status=code)

    def create(self, request, *args, **kwargs):
        raw = request.data.get("lead")
        lead = Lead.objects.filter(lead_access.visible_q(request.user), pk=int(raw) if str(raw or "").isdigit() else 0).first()
        if lead is None:
            raise NotFound("Record not found.")
        if not access.acts_on_lead(request.user, lead):
            raise PermissionDenied(MSG_NO_REQUEST)
        return self.out(services.request_contract(request.user, lead, request.data.get("note")), status.HTTP_201_CREATED)

    def _hr(self, request):
        if not access.is_hr(request.user):
            raise PermissionDenied(MSG_HR_ONLY)

    def _pipeline(self, request, c):
        if not access.on_pipeline(request.user, c):
            raise PermissionDenied(MSG_NO_PIPELINE)

    def _ceo(self, request):
        if not access.is_ceo(request.user):
            raise PermissionDenied(MSG_CEO_ONLY)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        self._hr(request)
        return self.out(services.start_drafting(request.user, self.get_object()))

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        self._hr(request)
        return self.out(services.send_to_commercial(request.user, self.get_object(), request.data.get("note")))

    @action(detail=True, methods=["post"])
    def meeting(self, request, pk=None):
        c = self.get_object()
        self._pipeline(request, c)
        raw = request.data.get("meeting_date")
        try:
            parsed = date.fromisoformat(str(raw)) if raw else None
        except ValueError:
            parsed = None
        return self.out(services.log_meeting(request.user, c, parsed, request.data.get("meeting_notes")))

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        c = self.get_object()
        self._pipeline(request, c)
        return self.out(services.submit_to_ceo(request.user, c))

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        self._ceo(request)
        return self.out(services.ceo_sign(request.user, self.get_object()))

    @action(detail=True, methods=["post"], url_path="return")
    def return_(self, request, pk=None):
        self._ceo(request)
        return self.out(services.ceo_return(request.user, self.get_object(), request.data.get("comment")))

    @action(detail=True, methods=["post"])
    def handover(self, request, pk=None):
        self._hr(request)
        return self.out(services.hand_over(request.user, self.get_object()))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        if not access.is_head(request.user):
            raise PermissionDenied(MSG_HEAD_ONLY)
        return self.out(services.cancel(request.user, self.get_object(), request.data.get("reason")))
