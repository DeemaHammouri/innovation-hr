from datetime import date, timedelta

from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import PasswordChangeNotPending
from contracts import access as contract_access
from contracts.models import Contract
from core.csvout import csv_response
from leads import access as lead_access
from leads.models import Lead
from leads.sla import sla_now
from operations import access as op_access
from clients.models import Client
from quotations import access as quote_access
from quotations.models import Quotation

from . import access, exports
from .builders import BUILDERS
from .series import csv_rows

MSG_DATES = "Choose valid dates."
MSG_RANGE = "Choose a period of up to 2 years."
MSG_FORMAT = "Choose csv, xlsx or pdf."
MSG_FORBIDDEN = "You don't have access to this report."
MAX_DAYS = 731
DEFAULT_DAYS = {"forecast": 365}


def parse_period(request, section):
    today = sla_now()[0]
    try:
        end = date.fromisoformat(request.query_params["to"]) if request.query_params.get("to") else today
        start = date.fromisoformat(request.query_params["from"]) if request.query_params.get("from") else end - timedelta(days=DEFAULT_DAYS.get(section, 90) - 1)
    except ValueError:
        raise ValidationError({"detail": MSG_DATES})
    if start > end:
        raise ValidationError({"detail": MSG_DATES})
    if (end - start).days > MAX_DAYS:
        raise ValidationError({"detail": MSG_RANGE})
    return start, end


class Base(APIView):
    def get_required_capabilities(self, request):
        section = self.kwargs.get("section")
        # An unknown section is answered with 404 by build(); a known one needs its own capability.
        return [f"report.{section}"] if section in access.SECTIONS else []

    denied_message = None

    def build(self, request, section):
        if section not in BUILDERS:
            raise NotFound()
        if not access.can_open(request.user, section):
            raise PermissionDenied(MSG_FORBIDDEN)
        start, end = parse_period(request, section)
        report = BUILDERS[section](request.user, start, end)
        report["period"] = {"from": str(start), "to": str(end)}
        return report


class ReportIndex(APIView):
    required_capabilities = []  # lists only the sections the person may open

    def get(self, request):
        return Response({"sections": access.sections_for(request.user)})


class ReportView(Base):
    def get(self, request, section):
        return Response(self.build(request, section))


class ReportExport(Base):
    def get(self, request, section):
        report = self.build(request, section)
        p = report["period"]
        rows = csv_rows(report)
        fmt = request.query_params.get("fmt", "csv")  # not "format": DRF keeps that name for content negotiation
        base = f"report-{section}-{p['from']}-{p['to']}"
        if fmt == "xlsx":
            return exports.xlsx_response(f"{base}.xlsx", rows)
        if fmt == "pdf":
            lang = "ar" if request.query_params.get("lang") == "ar" else "en"
            return exports.pdf_response(f"{base}.pdf", section, p, rows, lang)
        if fmt != "csv":
            raise ValidationError({"detail": MSG_FORMAT})
        return csv_response(f"{base}.csv", ["report", "series", "label", "value", "unit", "based_on_records"], rows)


class SearchView(APIView):
    """One box over leads, quotations, contracts and clients. Each kind goes through the same visibility rule as its own list, and
    only reference, company and contact fields are searched: no HR or payroll data is reachable from here."""

    required_capabilities = []  # each kind is filtered by its own module's visibility rule
    LIMIT = 5

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()[:100]
        if len(q) < 2:
            return Response({"q": q, "results": []})
        user, out = request.user, []
        if lead_access.has_lead_access(user):
            qs = Lead.objects.filter(lead_access.visible_q(user), archived_at__isnull=True).filter(Q(company_name__icontains=q) | Q(ref__icontains=q) | Q(contact_name__icontains=q))
            out += [{"kind": "lead", "id": x.id, "title": x.company_name, "subtitle": x.ref, "href": f"/leads/{x.id}"} for x in qs.order_by("-created_at")[: self.LIMIT]]
        if quote_access.has_access(user):
            qs = Quotation.objects.filter(quote_access.visible_q(user)).filter(Q(ref__icontains=q) | Q(lead__company_name__icontains=q)).select_related("lead")
            out += [{"kind": "quotation", "id": x.id, "title": x.lead.company_name, "subtitle": x.ref, "href": f"/quotations/{x.id}"} for x in qs.order_by("-created_at")[: self.LIMIT]]
        if contract_access.has_access(user):
            qs = Contract.objects.filter(contract_access.visible_q(user)).filter(Q(ref__icontains=q) | Q(lead__company_name__icontains=q)).select_related("lead")
            out += [{"kind": "contract", "id": x.id, "title": x.lead.company_name, "subtitle": x.ref, "href": f"/contracts/{x.id}"} for x in qs.order_by("-created_at")[: self.LIMIT]]
        if op_access.has_access(user):
            qs = Client.objects.filter(op_access.visible_clients_q(user)).filter(Q(company_name__icontains=q) | Q(contact_person__icontains=q))
            out += [{"kind": "client", "id": x.id, "title": x.company_name, "subtitle": x.contact_person, "href": f"/operation/{x.id}"} for x in qs.order_by("company_name")[: self.LIMIT]]
        return Response({"q": q, "results": out})
