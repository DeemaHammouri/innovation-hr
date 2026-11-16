"""Objective 18: Operation never receives prices, payment data, the contract text or the contract file.

Two kinds of proof. (1) Names: every JSON answer from every endpoint an Operation person can open is walked key by key, and none may be
a money field. (2) Values: the data is seeded with unmistakable amounts, and none of them may appear anywhere in any answer, however the
field is named. The walk covers every route in the API (the same list the permission audit uses), with ids 1 to 6 for detail routes."""
import json
import re
from datetime import timedelta

from django.utils import timezone

from contracts import services as cs
from contracts.models import Contract
from core.access import content_type_for
from core.permission_audit import endpoints
from core.testing import png_signature
from files.models import Attachment
from operations.tests_handover import HCase
from payments.models import Instalment, Payment
from quotations import services as qs

OP = ("operation_head", "operation_member")
MARKERS = ("7777.77", "6666.66", "8888.88", "7777", "6666", "8888")
# A key is money if any of its words is one of these (so `required_total` - a count of checklist items - is not, but `unit_price` is).
MONEY_WORDS = {"price", "amount", "subtotal", "discount", "tax", "currency", "payment", "payments", "balance", "invoice", "cost", "vat", "fee", "fees", "paid", "instalment", "instalments", "installment", "grand"}
NOT_MONEY = {"required_total", "total_tasks"}
# Operation's own HR records (leave, attendance, payslip) are about the employee, not about a client's deal.
OWN_HR_PREFIX = "/api/v1/hr/"


def body_of(res):
    raw = b"".join(res.streaming_content) if getattr(res, "streaming", False) else res.content
    return raw.decode("utf-8", "ignore")


def money_keys(node, path=""):
    found = []
    if isinstance(node, dict):
        for k, v in node.items():
            words = set(re.split(r"[_\W]+", k.lower()))
            totalish = k.lower() == "total" or k.lower().endswith("_total")
            if k not in NOT_MONEY and (words & MONEY_WORDS or (totalish and not isinstance(v, int))):  # a whole-number total is a count, money is a decimal string
                found.append(f"{path}.{k}")
            found += money_keys(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found += money_keys(v, f"{path}[{i}]")
    return found


class PrivacyCase(HCase):
    def setUp(self):
        super().setUp()
        self.hr2 = self.users["hr_member"]
        h = self.submitted("Money Co")
        self.call(self.ohead, h, "accept")
        self.h = Handover_get(h)
        self.contract = self.h.contract
        self.lead = self.contract.lead
        # a quotation that was sent, with real amounts in it
        self.lead.skipped_quotation_at = None
        self.lead.save(update_fields=["skipped_quotation_at"])
        q = qs.request_quotation(self.cmem, self.lead, "please")
        q = qs.start_preparing(self.hr2, q)
        qs.save_draft(self.hr2, q, {
            "currency": "JOD", "valid_until": (timezone.localdate() + timedelta(days=30)).isoformat(), "payment_terms": "Pay 8888.88 up front",
            "lines": [{"description": "Bookkeeping", "quantity": "1", "unit_price": "7777.77", "discount_percent": "0", "tax_percent": "0", "frequency": "monthly", "visits": 1}],
        })
        q = qs.submit(self.hr2, q)
        q = qs.sign(self.chead, q, png_signature())
        qs.mark_sent(self.cmem, q)
        # a contract whose text carries a price
        Contract.objects.filter(pk=self.contract.pk).update(status="drafting")
        c = Contract.objects.get(pk=self.contract.pk)
        v = c.versions.order_by("-number").first()
        if v is not None:
            v.body_en, v.body_ar = "The fee is 6666.66 JOD per month", "الأتعاب 6666.66"
            v.save()
        Contract.objects.filter(pk=self.contract.pk).update(status="handed_over")
        self.attachment = Attachment.objects.filter(content_type=content_type_for(Contract), object_id=self.contract.pk).first()
        inst = Instalment.objects.create(client=self.h.client, contract=self.contract, number=1, due_date=timezone.localdate(), amount="8888.88", created_by=self.ceo)
        Payment.objects.create(instalment=inst, amount="8888.88", received_on=timezone.localdate(), recorded_by=self.ceo)


def Handover_get(h):
    from operations.models import Handover

    return Handover.objects.select_related("contract__lead", "client").get(pk=h.pk)


class WhatOperationReceivesTests(PrivacyCase):
    def urls(self):
        out = []
        for url, _ in endpoints():
            if url.startswith(OWN_HR_PREFIX) or "/auth/" in url or url.endswith("/health/"):
                continue
            out.append(url)
            if "/1/" in url:
                out += [url.replace("/1/", f"/{k}/", 1) for k in range(2, 7)]
        return out

    def test_no_answer_to_operation_holds_a_money_field_or_a_seeded_amount(self):
        checked = 0
        problems = []
        for key in OP:
            self.as_role(key)
            for url in self.urls():
                for query in ("", "?fmt=pdf&lang=both", "?lead=%d" % self.lead.pk, "?target=contract:%d" % self.contract.pk):
                    res = self.client.get(url + query)
                    if res.status_code != 200:
                        continue
                    checked += 1
                    raw = body_of(res)
                    for m in MARKERS:
                        if m in raw:
                            problems.append(f"{key} GET {url}{query} contains {m}")
                    try:
                        body = json.loads(raw)
                    except ValueError:
                        continue
                    for found in money_keys(body):
                        problems.append(f"{key} GET {url}{query} has money field {found}")
        self.assertGreater(checked, 20, "the walk should have reached the Operation endpoints")
        import re as _re

        distinct = sorted({_re.sub(r"\[\d+\]", "[]", _re.sub(r"/\d+/", "/N/", p)) for p in problems})
        self.maxDiff = None
        self.assertEqual(distinct, [])

    def test_the_walk_can_actually_see_money(self):
        """Guards the test above: the same walk as the CEO does find the seeded amounts, so a clean run for Operation means something."""
        self.as_role("ceo")
        hits = 0
        for url in self.urls():
            res = self.client.get(url)
            if res.status_code == 200 and any(m in body_of(res) for m in MARKERS):
                hits += 1
        self.assertGreaterEqual(hits, 1)
        self.assertTrue(money_keys({"items": [{"unit_price": 1}]}))
        self.assertFalse(money_keys({"required_total": 3, "status": "ok"}))


class ContractFileIsUnreachableTests(PrivacyCase):
    def test_operation_cannot_open_the_contract_or_anything_attached_to_it(self):
        for key in OP:
            self.as_role(key)
            c = self.client
            for url in (
                f"/api/contracts/{self.contract.pk}/", "/api/contracts/", f"/api/contracts/{self.contract.pk}/document/?fmt=pdf", f"/api/contracts/{self.contract.pk}/document/?fmt=docx",
                f"/api/files/?target=contract:{self.contract.pk}", f"/api/files/{self.attachment.pk}/download/", f"/api/activity/?target=contract:{self.contract.pk}",
                f"/api/comments/?target=contract:{self.contract.pk}", f"/api/files/?target=quotation:1", "/api/contract-templates/",
            ):
                res = c.get(url)
                self.assertIn(res.status_code, (403, 404), f"{key} GET {url} -> {res.status_code}")
            # the lead's Documents tab lists nothing of the deal
            res = c.get(f"/api/documents/?lead={self.lead.pk}")
            self.assertIn(res.status_code, (403, 404))

    def test_operation_cannot_attach_to_a_handover_or_a_contract(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        for key in OP:
            self.as_role(key)
            for target in (f"handover:{self.h.pk}", f"contract:{self.contract.pk}", f"project:{self.h.project.pk}"):
                res = self.client.post(f"/api/files/?target={target}", {"file": SimpleUploadedFile("x.pdf", b"%PDF-1.4", "application/pdf"), "category": "kyc"}, format="multipart")
                self.assertIn(res.status_code, (400, 403, 404), f"{key} {target} -> {res.status_code}")
        self.assertEqual(Attachment.objects.filter(content_type=content_type_for(Contract), object_id=self.contract.pk).count(), 1)

    def test_the_contract_is_still_reachable_by_the_people_who_own_it(self):
        for key in ("ceo", "commercial_head", "hr_head"):
            self.as_role(key)
            self.assertEqual(self.client.get(f"/api/contracts/{self.contract.pk}/").status_code, 200, key)

    def test_search_never_turns_up_the_contract_for_operation(self):
        for key in OP:
            self.as_role(key)
            res = self.client.get("/api/search/", {"q": "Money Co"})
            self.assertEqual(res.status_code, 200)
            raw = json.dumps(res.data)
            self.assertNotIn(self.contract.ref, raw)
            self.assertNotIn("contract", [r.get("kind") for g in (res.data if isinstance(res.data, list) else res.data.get("groups", [])) for r in (g.get("results", []) if isinstance(g, dict) else [])])


class ServicePriceListTests(PrivacyCase):
    def test_the_service_names_are_for_everyone_but_the_price_list_is_not(self):
        from lookups.models import Service

        Service.objects.create(name_en="Audit", name_ar="تدقيق", default_unit_price="7777.77", currency="JOD")
        for key in OP + ("marketing", "commercial_member", "commercial_head"):
            self.as_role(key)
            row = next(r for r in self.client.get("/api/lookups/services/").data if r["name_en"] == "Audit")
            self.assertEqual((row["name_en"], "default_unit_price" in row, "currency" in row), ("Audit", False, False), key)
        for key in ("ceo", "hr_head", "hr_member"):
            self.as_role(key)
            row = next(r for r in self.client.get("/api/lookups/services/").data if r["name_en"] == "Audit")
            self.assertEqual(row["default_unit_price"], "7777.77", key)
