from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.settings import api_settings

from core.pagination import StandardPagination
from leads import access as lead_access
from leads.models import Lead

from documents import builders as doc_builders
from documents import serve as doc_serve

from . import access, services
from .filters import ContractFilter
from .models import Contract, ContractTemplate
from .serializers import ContractDetailSerializer, ContractSerializer

MSG_NO_REQUEST = "You can't request a contract for this lead."
MSG_HR_ONLY = "Only HR can prepare contracts."
MSG_HEAD_ONLY = "Only the Commercial head can do this."
MSG_CEO_ONLY = "Only the CEO can do this."
MSG_NO_PIPELINE = "Only the Commercial head or the assigned member can do this."

RELATED = ("lead", "lead__assigned_to", "quotation", "requested_by", "drafted_by", "signed_by", "handed_over_by")


class ContractViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    required_capabilities = {
        "*": ["contract.access"],
        "start": ["contract.access", "contract.draft"], "send": ["contract.access", "contract.draft"], "handover": ["contract.access", "contract.draft"],
        "draft": ["contract.access", "contract.draft"], "send_to_client": ["contract.access", "contract.draft"],
        "confirm": ["contract.access", "contract.confirm"], "commercial_return": ["contract.access", "contract.confirm"],
        "approve": ["contract.access", "contract.sign"], "return_": ["contract.access", "contract.sign"],
    }
    denied_message = {
        "*": "You don't have access to contracts.",
        "start": MSG_HR_ONLY, "send": MSG_HR_ONLY, "handover": MSG_HR_ONLY, "draft": MSG_HR_ONLY, "send_to_client": MSG_HR_ONLY,
        "confirm": MSG_HEAD_ONLY, "commercial_return": MSG_HEAD_ONLY, "approve": MSG_CEO_ONLY, "return_": MSG_CEO_ONLY,
    }
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ContractFilter
    search_fields = ["ref", "lead__company_name", "lead__ref", "lead__contact_name"]
    ordering_fields = ["created_at", "status"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Contract.objects.none()
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
        if not access.signs_contracts(request.user):
            raise PermissionDenied(MSG_CEO_ONLY)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        self._hr(request)
        return self.out(services.start_drafting(request.user, self.get_object()))

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        self._hr(request)
        return self.out(services.send_to_commercial(request.user, self.get_object(), request.data.get("note")))

    @action(detail=True, methods=["post", "patch"])
    def draft(self, request, pk=None):
        self._hr(request)
        return self.out(services.save_draft(request.user, self.get_object(), request.data))

    @action(detail=True, methods=["post"], url_path="commercial-return")
    def commercial_return(self, request, pk=None):
        return self.out(services.return_to_hr(request.user, self.get_object(), request.data.get("comment")))

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self.out(services.confirm(request.user, self.get_object()))

    @action(detail=True, methods=["post"], url_path="send-to-client")
    def send_to_client(self, request, pk=None):
        self._hr(request)
        return self.out(services.send_to_client(request.user, self.get_object()))

    @action(detail=True, methods=["post"], url_path="client-copy", parser_classes=[MultiPartParser, FormParser])
    def client_copy(self, request, pk=None):
        c = self.get_object()
        if not access.can_attach(request.user, c, "client_signed_copy"):
            raise PermissionDenied(MSG_NO_PIPELINE)
        return self.out(services.upload_client_copy(request.user, c, request.FILES.get("file")))

    @action(detail=True, methods=["get"])
    def document(self, request, pk=None):
        """The contract as a branded PDF or Word file. The client's uploaded signed copy or the CEO's final copy replaces the generated PDF."""
        c = self.get_object()
        fmt, lang = doc_serve.options(request)
        override = None if request.query_params.get("generated") == "1" else doc_builders.signed_copy(c, "final_signed", "client_signed_copy")
        return doc_serve.respond(doc_builders.build_contract(c, lang), fmt, lang, override)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser, *api_settings.DEFAULT_PARSER_CLASSES])
    def approve(self, request, pk=None):
        self._ceo(request)
        return self.out(services.ceo_sign(request.user, self.get_object(), request.data.get("signature"), request.FILES.get("file")))

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


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContractTemplate
        fields = ["id", "country", "name_en", "name_ar", "body_en", "body_ar", "is_active", "updated_at"]
        read_only_fields = ["id", "updated_at"]

    def validate_country(self, value):
        from clients.countries import CODES

        if value != "*" and value not in CODES:
            raise serializers.ValidationError("Choose a country from the list, or * for the default.")
        return value

    def validate(self, attrs):
        for k in ("body_en", "body_ar", "name_en", "name_ar"):
            if k in attrs and not str(attrs[k]).strip():
                raise serializers.ValidationError({k: "This can't be empty."})
        return attrs


class ContractTemplateViewSet(viewsets.ModelViewSet):
    """The contract wording for each country. Everyone who opens contracts can read them; HR and the CEO edit."""

    required_capabilities = {"*": ["contract.template"], "list": ["contract.access"], "retrieve": ["contract.access"]}
    denied_message = {"*": "Only HR and the CEO can change contract templates.", "list": "You don't have access to contracts.", "retrieve": "You don't have access to contracts."}
    queryset = ContractTemplate.objects.all()
    serializer_class = TemplateSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
