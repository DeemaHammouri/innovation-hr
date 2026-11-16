from collections import defaultdict
from decimal import Decimal

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from clients.models import Client
from core.csvout import csv_response
from core.pagination import StandardPagination
from leads.sla import sla_now

from . import access, services
from .models import Instalment, Payment
from .serializers import InstalmentSerializer, PaymentSerializer, money, receipt_ids

MSG_HEAD_ONLY = "Only the Commercial head can do this."


class Base:
    required_capabilities = {"*": ["payment.view"]}
    denied_message = "You don't have access to payments."

    def today(self):
        return sla_now()[0]

    def need_head(self, request):
        if not access.is_head(request.user):
            raise PermissionDenied(MSG_HEAD_ONLY)

    def ctx(self, request):
        return {"request": request, "today": self.today()}

    def client_or_404(self, pk):
        client = Client.objects.filter(pk=int(pk) if str(pk).isdigit() else 0).first()
        if client is None:
            raise NotFound("Record not found.")
        return client


def statement_payload(request, client, today):
    insts, pays, totals = services.statement(client, today)
    ctx = {"request": request, "today": today, "receipts": receipt_ids(pays)}
    currency = insts[0].currency if insts else "JOD"
    return {
        "client": {"id": client.pk, "company_name": client.company_name},
        "currency": currency,
        "totals": {k: (money(v) if isinstance(v, Decimal) else v) for k, v in totals.items()},
        "instalments": InstalmentSerializer(insts, many=True, context=ctx).data,
        "payments": PaymentSerializer(sorted(pays, key=lambda p: (p.received_on, p.pk), reverse=True), many=True, context=ctx).data,
        "permissions": {"can_write": access.can_write(request.user)},
    }


class OverviewView(Base, APIView):
    """GET /api/payments/overview/ - one row per client with a schedule: totals, balance, overdue."""

    pagination_class = StandardPagination

    def get(self, request):
        today = self.today()
        qs = services.with_paid(Instalment.objects.select_related("client"))
        term = (request.query_params.get("search") or "").strip()
        if term:
            qs = qs.filter(Q(client__company_name__icontains=term) | Q(client__contact_person__icontains=term))
        groups = defaultdict(list)
        for inst in qs:
            groups[inst.client_id].append(inst)
        rows = []
        for cid, insts in groups.items():
            t = services.summarise(insts, today)
            rows.append({
                "client": cid, "company_name": insts[0].client.company_name, "currency": insts[0].currency,
                "instalments": sum(1 for i in insts if not i.cancelled_at), **{k: (money(v) if isinstance(v, Decimal) else v) for k, v in t.items()},
                "_balance": t["balance"],
            })
        flt = request.query_params.get("filter")
        if flt == "overdue":
            rows = [r for r in rows if r["overdue_count"]]
        elif flt == "open":
            rows = [r for r in rows if r["_balance"] > 0]
        elif flt == "settled":
            rows = [r for r in rows if r["_balance"] == 0]
        rows.sort(key=lambda r: (-r["overdue_count"], -r["_balance"], r["company_name"].lower()))
        for r in rows:
            r.pop("_balance")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(page)


class ClientPaymentsViewSet(Base, viewsets.ViewSet):
    """/api/payments/clients/<id>/ ..."""

    def retrieve(self, request, pk=None):
        return Response(statement_payload(request, self.client_or_404(pk), self.today()))

    @action(detail=True, methods=["get"], url_path="export")
    def export(self, request, pk=None):
        client = self.client_or_404(pk)
        insts, pays, totals = services.statement(client, self.today())
        today = self.today()
        rows = [["Instalment", i.number, i.due_date, i.currency, money(i.amount), money(i.paid), services.status_of(i, i.paid, today), i.note] for i in insts]
        rows += [[("Reversal" if p.kind == "reversal" else "Payment"), p.instalment.number, p.received_on, p.instalment.currency, money(-p.amount if p.kind == "reversal" else p.amount), p.method, p.reference, p.reason] for p in pays]
        rows.append(["Total", "", "", "", money(totals["total"]), money(totals["paid"]), "balance " + money(totals["balance"]), ""])
        return csv_response(f"statement-{client.pk}.csv", ["Type", "No.", "Date", "Currency", "Amount", "Paid / method", "Status / reference", "Note / reason"], rows)

    @action(detail=True, methods=["post"], url_path="schedule")
    def schedule(self, request, pk=None):
        self.need_head(request)
        services.create_schedule(request.user, self.client_or_404(pk), request.data)
        return Response(statement_payload(request, self.client_or_404(pk), self.today()), status=status.HTTP_201_CREATED)


class InstalmentViewSet(Base, viewsets.ViewSet):
    def get_inst(self, pk):
        inst = services.with_paid(Instalment.objects.filter(pk=int(pk) if str(pk).isdigit() else 0)).first()
        if inst is None:
            raise NotFound("Record not found.")
        return inst

    def out(self, request, inst, code=status.HTTP_200_OK):
        return Response(statement_payload(request, inst.client, self.today()), status=code)

    def partial_update(self, request, pk=None):
        self.need_head(request)
        inst = services.update_instalment(request.user, self.get_inst(pk), request.data)
        return self.out(request, inst)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        self.need_head(request)
        return self.out(request, services.cancel_instalment(request.user, self.get_inst(pk), request.data.get("reason")))

    @action(detail=True, methods=["post"], url_path="payments")
    def pay(self, request, pk=None):
        self.need_head(request)
        inst = self.get_inst(pk)
        services.record_payment(request.user, inst, request.data, self.today())
        payload = statement_payload(request, inst.client, self.today())
        payload["recorded"] = max((p["id"] for p in payload["payments"]), default=None)
        return Response(payload, status=status.HTTP_201_CREATED)


class PaymentViewSet(Base, viewsets.ViewSet):
    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        self.need_head(request)
        pay = get_object_or_404(Payment.objects.select_related("instalment__client"), pk=int(pk) if str(pk).isdigit() else 0)
        services.reverse_payment(request.user, pay, request.data.get("reason"), self.today())
        return Response(statement_payload(request, pay.instalment.client, self.today()), status=status.HTTP_201_CREATED)
