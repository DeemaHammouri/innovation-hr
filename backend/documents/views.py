"""The Documents tab of a client: every quotation, contract and meeting report of their lead, with each version, and only the ones
the signed-in person may see (each kind keeps its own visibility rule)."""
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from contracts import access as contract_access
from contracts.models import Contract
from leads import access as lead_access
from leads.models import Lead
from meetings import access as report_access
from meetings.models import MeetingReport
from quotations import access as quotation_access
from quotations.models import Quotation


def _who(user):
    return user.full_name if user else None


class ClientDocumentsView(APIView):
    """GET /api/documents/?lead=<id> (or ?client=<id>)."""

    required_capabilities = {"get": []}
    denied_message = "You can't see documents."

    def get(self, request):
        from clients.models import Client

        raw = request.query_params
        client = Client.objects.filter(pk=int(raw["client"])).select_related("lead").first() if raw.get("client", "").isdigit() else None
        lead = client.lead if client else (Lead.objects.filter(pk=int(raw["lead"])).first() if raw.get("lead", "").isdigit() else None)
        user = request.user
        if lead is None or not (lead_access.can_view(user, lead) or client_visible(user, client)):
            raise NotFound("Record not found.")
        items = []
        for q in Quotation.objects.filter(quotation_access.visible_q(user), lead=lead).prefetch_related("versions__created_by"):
            items.append({
                "kind": "quotation", "id": q.pk, "ref": q.number or q.ref, "status": q.status, "date": q.sent_at or q.created_at,
                "link": f"/quotations/{q.pk}", "download": f"/quotations/{q.pk}/document/",
                "versions": [{"number": v.number, "date": v.created_at, "by": _who(v.created_by), "total": str(v.total), "currency": v.currency} for v in q.versions.all()],
            })
        for c in Contract.objects.filter(contract_access.visible_q(user), lead=lead).prefetch_related("versions__created_by"):
            items.append({
                "kind": "contract", "id": c.pk, "ref": c.number or c.ref, "status": c.status, "date": c.sent_at or c.created_at,
                "link": f"/contracts/{c.pk}", "download": f"/contracts/{c.pk}/document/",
                "versions": [{"number": v.number, "date": v.created_at, "by": _who(v.created_by), "total": str(v.total), "currency": v.currency} for v in c.versions.all()],
            })
        for r in MeetingReport.objects.filter(report_access.visible_q(user), lead=lead).select_related("author"):
            items.append({
                "kind": "meeting_report", "id": r.pk, "ref": f"MR-{r.pk:05d}", "status": r.status, "date": r.created_at,
                "link": f"/meetings/{r.pk}", "download": f"/meeting-reports/{r.pk}/document/", "versions": [{"number": 1, "date": r.updated_at, "by": _who(r.author)}],
            })
        items.sort(key=lambda i: i["date"], reverse=True)
        return Response({"lead": lead.pk, "company": lead.company_name, "items": items})


def client_visible(user, client):
    return bool(client and user.has_capability("client.manage"))
