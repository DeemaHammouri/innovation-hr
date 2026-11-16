"""What a client sees when they sign in. Every query starts from the client linked to the signed-in account, so there is no id in
any URL a client could change to reach somebody else's data."""
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Client


class PortalClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "company_name", "contact_person", "phone", "email", "address"]
        read_only_fields = fields


def my_client(request):
    return get_object_or_404(Client, portal_user=request.user)


class PortalMeView(APIView):
    required_capabilities = ["portal.access"]
    denied_message = "This area is for clients."

    def get(self, request):
        client = my_client(request)
        return Response({"client": PortalClientSerializer(client).data})


# ---------- the client's quotations ----------
from quotations import services as quotation_services  # noqa: E402
from quotations.models import Quotation  # noqa: E402

CLIENT_VISIBLE = ["sent", "waiting", "confirmed"]


class PortalQuotationSerializer(serializers.ModelSerializer):
    """What the client may see: the signed offer, never internal notes, review comments or who prepared it."""

    company = serializers.CharField(source="lead.company_name", read_only=True)
    version = serializers.SerializerMethodField()
    can_sign = serializers.SerializerMethodField()

    class Meta:
        model = Quotation
        fields = ["id", "number", "status", "company", "sent_at", "client_signed_at", "client_signed_via", "version", "can_sign"]
        read_only_fields = fields

    def get_version(self, q):
        v = next((x for x in q.versions.all() if x.number == q.signed_version), None)
        if v is None:
            return None
        return {
            "number": v.number, "currency": v.currency, "valid_until": v.valid_until, "payment_terms": v.payment_terms, "notes": v.notes,
            "subtotal": str(v.subtotal), "discount_total": str(v.discount_total), "tax_total": str(v.tax_total), "total": str(v.total),
            "lines": [{"description": l.description, "quantity": str(l.quantity), "unit_price": str(l.unit_price), "discount_percent": str(l.discount_percent),
                       "tax_percent": str(l.tax_percent), "line_total": str(l.line_total), "frequency": l.frequency, "visits": l.visits} for l in v.lines.all()],
        }

    def get_can_sign(self, q):
        return q.status in ("sent", "waiting") and not q.client_signed_at


def _mine(request):
    client = my_client(request)
    qs = Quotation.objects.filter(lead__client=client, status__in=CLIENT_VISIBLE).select_related("lead").prefetch_related("versions__lines")
    return qs


class PortalQuotationListView(APIView):
    required_capabilities = ["portal.access"]
    denied_message = "This area is for clients."

    def get(self, request):
        return Response(PortalQuotationSerializer(_mine(request).order_by("-sent_at", "-id"), many=True).data)


class PortalQuotationDetailView(APIView):
    required_capabilities = ["portal.access"]
    denied_message = "This area is for clients."

    def get(self, request, pk):
        return Response(PortalQuotationSerializer(get_object_or_404(_mine(request), pk=pk)).data)


class PortalQuotationDocumentView(APIView):
    required_capabilities = ["portal.access"]
    denied_message = "This area is for clients."

    def get(self, request, pk):
        from documents import builders, serve

        q = get_object_or_404(_mine(request), pk=pk)
        fmt, lang = serve.options(request)
        return serve.respond(builders.build_quotation(q), fmt, lang, builders.signed_copy(q))


class PortalQuotationSignView(APIView):
    required_capabilities = {"post": ["portal.access"]}
    denied_message = "This area is for clients."

    def post(self, request, pk):
        q = get_object_or_404(_mine(request), pk=pk)
        quotation_services.client_sign(request.user, q, request.data.get("signature"))
        return Response(PortalQuotationSerializer(get_object_or_404(_mine(request), pk=pk)).data)


# ---------- the client's contracts ----------
from contracts import services as contract_services  # noqa: E402
from contracts.models import Contract  # noqa: E402

CONTRACT_VISIBLE = ["sent", "ceo_review", "signed", "handed_over"]


class PortalContractSerializer(serializers.ModelSerializer):
    """What the client may see of a contract: the text that was sent, the number and the signing state. No internal notes."""

    company = serializers.CharField(source="lead.company_name", read_only=True)
    version = serializers.SerializerMethodField()
    can_sign = serializers.SerializerMethodField()

    class Meta:
        model = Contract
        fields = ["id", "number", "status", "company", "sent_at", "client_signed_at", "client_signed_via", "signed_at", "version", "can_sign"]
        read_only_fields = fields

    def get_version(self, c):
        v = c.versions.exclude(submitted_at=None).order_by("-number").first()
        if v is None:
            return None
        return {"number": v.number, "title": v.title, "currency": v.currency, "total": str(v.total), "payment_terms": v.payment_terms, "start_date": v.start_date, "end_date": v.end_date, "body_en": v.body_en, "body_ar": v.body_ar, "services": v.services}

    def get_can_sign(self, c):
        return c.status == "sent" and not c.client_signed_at


def _my_contracts(request):
    client = my_client(request)
    return Contract.objects.filter(lead__client=client, status__in=CONTRACT_VISIBLE).select_related("lead").prefetch_related("versions")


class PortalContractListView(APIView):
    required_capabilities = ["portal.access"]
    denied_message = "This area is for clients."

    def get(self, request):
        return Response(PortalContractSerializer(_my_contracts(request).order_by("-sent_at", "-id"), many=True).data)


class PortalContractDetailView(APIView):
    required_capabilities = ["portal.access"]
    denied_message = "This area is for clients."

    def get(self, request, pk):
        return Response(PortalContractSerializer(get_object_or_404(_my_contracts(request), pk=pk)).data)


class PortalContractDocumentView(APIView):
    required_capabilities = ["portal.access"]
    denied_message = "This area is for clients."

    def get(self, request, pk):
        from documents import builders, serve

        c = get_object_or_404(_my_contracts(request), pk=pk)
        fmt, lang = serve.options(request)
        return serve.respond(builders.build_contract(c, lang), fmt, lang, builders.signed_copy(c, "final_signed", "client_signed_copy"))


class PortalContractSignView(APIView):
    required_capabilities = {"post": ["portal.access"]}
    denied_message = "This area is for clients."

    def post(self, request, pk):
        c = get_object_or_404(_my_contracts(request), pk=pk)
        contract_services.client_sign(request.user, c, request.data.get("signature"))
        return Response(PortalContractSerializer(get_object_or_404(_my_contracts(request), pk=pk)).data)


# ---------- files Operation published to the client ----------
class PortalDeliverableSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    published_at = serializers.DateTimeField()
    acknowledged_at = serializers.DateTimeField(allow_null=True)
    filename = serializers.CharField(source="attachment.original_name")


def _my_deliverables(request):
    from operations.models import Deliverable

    return Deliverable.objects.filter(client=my_client(request)).select_related("attachment")


class PortalDeliverableListView(APIView):
    required_capabilities = ["portal.access"]
    denied_message = "This area is for clients."

    def get(self, request):
        return Response(PortalDeliverableSerializer(_my_deliverables(request), many=True).data)


class PortalDeliverableDownloadView(APIView):
    required_capabilities = ["portal.access"]
    denied_message = "This area is for clients."

    def get(self, request, pk):
        from django.http import FileResponse

        att = get_object_or_404(_my_deliverables(request), pk=pk).attachment
        res = FileResponse(att.file.open("rb"), as_attachment=True, filename=att.original_name, content_type=att.content_type_header)
        res["X-Content-Type-Options"] = "nosniff"
        res["Cache-Control"] = "private, no-store"
        return res


class PortalDeliverableAcknowledgeView(APIView):
    required_capabilities = {"post": ["portal.access"]}
    denied_message = "This area is for clients."

    def post(self, request, pk):
        from operations import lifecycle

        d = lifecycle.acknowledge(request.user, get_object_or_404(_my_deliverables(request), pk=pk))
        return Response(PortalDeliverableSerializer(d).data)

