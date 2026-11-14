from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from audit.models import AuditEntry
from clients.models import Client
from core.access import content_type_for
from core.roles import ALL_ROLES
from core.testing import RoleCase
from notifications.models import Notification
from payments import services
from payments.models import Instalment, LedgerError, Payment

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
TODAY = lambda: timezone.localdate()
D = lambda n: (TODAY() + timedelta(days=n)).isoformat()


class PCase(RoleCase):
    def setUp(self):
        super().setUp()
        self.ceo, self.head, self.member = self.users["ceo"], self.users["commercial_head"], self.users["commercial_member"]
        self.n = 0

    def mk(self):
        self.n += 1
        return Client.objects.create(company_name=f"Pay Client {self.n}", created_by=self.ceo)

    def schedule(self, client=None, rows=None, user=None, **extra):
        client = client or self.mk()
        rows = rows if rows is not None else [{"due_date": D(30), "amount": "100.00"}, {"due_date": D(60), "amount": "50"}]
        self.as_user(user or self.head)
        res = self.client.post(f"/api/payments/clients/{client.pk}/schedule/", {"instalments": rows, "currency": "JOD", **extra}, format="json")
        return client, res

    def inst(self, client, i=0):
        return client.instalments.order_by("number")[i]

    def pay(self, inst, amount="40", user=None, **extra):
        self.as_user(user or self.head)
        body = {"amount": amount, "received_on": TODAY().isoformat(), "method": "cash", **extra}
        return self.client.post(f"/api/payments/instalments/{inst.pk}/payments/", body, format="json")

    def statement(self, client, user=None):
        self.as_user(user or self.head)
        return self.client.get(f"/api/payments/clients/{client.pk}/")

    def row(self, client, n=0):
        return self.statement(client).data["instalments"][n]


class AccessTests(PCase):
    def test_read_rows(self):
        c, _ = self.schedule()
        read = {"ceo": 200, "commercial_head": 200, "*": 403}
        self.assert_matrix("get", "/api/payments/overview/", read)
        self.assert_matrix("get", f"/api/payments/clients/{c.pk}/", read)
        self.assert_matrix("get", f"/api/payments/clients/{c.pk}/export/", read)

    def test_write_rows(self):
        c = self.mk()
        rows = {"instalments": [{"due_date": D(5), "amount": "10"}]}
        self.assert_matrix("post", f"/api/payments/clients/{c.pk}/schedule/", {"commercial_head": 201, "*": 403}, data=rows)
        i = self.inst(c)
        self.assert_matrix("post", f"/api/payments/instalments/{i.pk}/payments/", {"commercial_head": 201, "*": 403}, data={"amount": "1", "received_on": D(0)})
        self.assert_matrix("patch", f"/api/payments/instalments/{i.pk}/", {"commercial_head": 400, "*": 403}, data={"amount": "5"})  # head allowed, but it has payments now
        self.assert_matrix("post", f"/api/payments/instalments/{i.pk}/cancel/", {"commercial_head": 400, "*": 403}, data={"reason": "x"})
        p = i.payments.first()
        self.assert_matrix("post", f"/api/payments/records/{p.pk}/reverse/", {"commercial_head": 201, "*": 403}, data={"reason": "Wrong amount"})

    def test_the_ceo_cannot_write(self):
        c, _ = self.schedule()
        i = self.inst(c)
        self.assertEqual(self.pay(i, user=self.ceo).status_code, 403)
        self.assertEqual(Payment.objects.count(), 0)

    def test_generic_endpoints_follow_the_same_rule(self):
        c, _ = self.schedule()
        i = self.inst(c)
        pay = Payment.objects.get(pk=self.pay(i).data["recorded"])
        for target in (f"instalment:{i.pk}", f"payment:{pay.pk}"):
            self.assert_matrix("get", f"/api/activity/?target={target}", {"ceo": 200, "commercial_head": 200, "*": 404})
            self.assert_matrix("get", f"/api/comments/?target={target}", {"ceo": 200, "commercial_head": 200, "*": 404})
            self.assert_matrix("get", f"/api/files/?target={target}", {"ceo": 200, "commercial_head": 200, "*": 404})

    def test_receipt_upload_and_flag(self):
        c, _ = self.schedule()
        pay = Payment.objects.get(pk=self.pay(self.inst(c)).data["recorded"])
        self.assertFalse(self.statement(c).data["payments"][0]["has_receipt"])
        self.as_user(self.head)
        up = self.client.post(f"/api/files/?target=payment:{pay.pk}", {"file": SimpleUploadedFile("r.pdf", PDF, content_type="application/pdf"), "category": "receipt"}, format="multipart")
        self.assertEqual(up.status_code, 201)
        self.assertTrue(self.statement(c).data["payments"][0]["has_receipt"])
        self.as_user(self.ceo)  # CEO may read the receipt but not add one
        self.assertEqual(self.client.get(f"/api/files/{up.data['id']}/download/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/files/?target=payment:{pay.pk}", {"file": SimpleUploadedFile("r2.pdf", PDF)}, format="multipart").status_code, 403)
        self.as_role("operation_head")
        self.assertEqual(self.client.get(f"/api/files/{up.data['id']}/download/").status_code, 404)

    def test_unknown_ids_are_404(self):
        self.as_user(self.head)
        self.assertEqual(self.client.get("/api/payments/clients/9999/").status_code, 404)
        self.assertEqual(self.client.post("/api/payments/instalments/9999/payments/", {}, format="json").status_code, 404)
        self.assertEqual(self.client.post("/api/payments/records/9999/reverse/", {}, format="json").status_code, 404)


class ScheduleTests(PCase):
    def test_create_numbers_and_sorts(self):
        c, res = self.schedule(rows=[{"due_date": D(60), "amount": "50"}, {"due_date": D(30), "amount": "100.5", "note": "Deposit"}])
        self.assertEqual(res.status_code, 201)
        rows = res.data["instalments"]
        self.assertEqual([(r["number"], r["amount"], r["status"]) for r in rows], [(1, "100.50", "expected"), (2, "50.00", "expected")])
        self.assertEqual(res.data["totals"]["total"], "150.50")
        self.assertEqual(res.data["totals"]["balance"], "150.50")
        _, again = self.schedule(client=c, rows=[{"due_date": D(90), "amount": "10"}])
        self.assertEqual(again.data["instalments"][-1]["number"], 3)
        self.assertEqual(AuditEntry.objects.filter(content_type=content_type_for(Instalment), action="created").count(), 3)

    def test_validation(self):
        c = self.mk()
        bad = [
            ({"instalments": []}, "instalments"), ({"instalments": "x"}, "instalments"), ({}, "instalments"),
            ({"instalments": [{"due_date": D(1), "amount": "10"}] * 37}, "instalments"),
            ({"instalments": [{"due_date": "soon", "amount": "10"}]}, "instalments"),
            ({"instalments": [{"due_date": D(1), "amount": "0"}]}, "instalments"),
            ({"instalments": [{"due_date": D(1), "amount": "-5"}]}, "instalments"),
            ({"instalments": [{"due_date": D(1), "amount": "abc"}]}, "instalments"),
            ({"instalments": [{"due_date": D(1), "amount": "NaN"}]}, "instalments"),
            ({"instalments": [{"due_date": D(1), "amount": "99999999999"}]}, "instalments"),
            ({"instalments": [{"due_date": D(1), "amount": "5", "note": "x" * 201}]}, "instalments"),
            ({"instalments": [{"due_date": D(1), "amount": "5"}], "currency": "JODD"}, "currency"),
            ({"instalments": [{"due_date": D(1), "amount": "5"}], "currency": "12"}, "currency"),
            ({"instalments": [{"due_date": D(1), "amount": "5"}], "contract": 999}, "contract"),
        ]
        self.as_user(self.head)
        for body, field in bad:
            res = self.client.post(f"/api/payments/clients/{c.pk}/schedule/", body, format="json")
            self.assertEqual(res.status_code, 400, body)
            self.assertIn(field, res.data, body)
        self.assertEqual(Instalment.objects.count(), 0)

    def test_row_errors_point_at_the_row(self):
        c, res = self.schedule(rows=[{"due_date": D(1), "amount": "5"}, {"due_date": D(2), "amount": "zero"}])
        self.assertEqual(res.data["instalments"], [{}, {"amount": services.MSG_AMOUNT}])

    def test_one_currency_per_client(self):
        c, _ = self.schedule()
        self.as_user(self.head)
        res = self.client.post(f"/api/payments/clients/{c.pk}/schedule/", {"instalments": [{"due_date": D(1), "amount": "5"}], "currency": "usd"}, format="json")
        self.assertEqual(res.data["currency"], services.MSG_CURRENCY_MIX)

    def test_edit_only_before_payments(self):
        c, _ = self.schedule()
        a, b = self.inst(c, 0), self.inst(c, 1)
        self.as_user(self.head)
        res = self.client.patch(f"/api/payments/instalments/{a.pk}/", {"amount": "120", "due_date": D(40), "note": "Moved"}, format="json")
        self.assertEqual((res.status_code, res.data["instalments"][0]["amount"]), (200, "120.00"))
        self.assertIn("amount", self.client.patch(f"/api/payments/instalments/{a.pk}/", {"amount": "0"}, format="json").data)
        self.assertIn("due_date", self.client.patch(f"/api/payments/instalments/{a.pk}/", {"due_date": "x"}, format="json").data)
        self.assertIn("note", self.client.patch(f"/api/payments/instalments/{a.pk}/", {"note": "x" * 201}, format="json").data)
        self.pay(b, "10")
        res = self.client.patch(f"/api/payments/instalments/{b.pk}/", {"amount": "70"}, format="json")
        self.assertEqual(res.data["detail"], services.MSG_HAS_PAYMENTS)
        self.assertFalse(next(r for r in self.statement(c).data["instalments"] if r["id"] == b.pk)["can_edit"])

    def test_cancel_rules(self):
        c, _ = self.schedule()
        a, b = self.inst(c, 0), self.inst(c, 1)
        self.as_user(self.head)
        self.assertEqual(self.client.post(f"/api/payments/instalments/{a.pk}/cancel/", {"reason": " "}, format="json").data["reason"], services.MSG_CANCEL_REASON)
        self.assertEqual(self.client.post(f"/api/payments/instalments/{a.pk}/cancel/", {"reason": "Renegotiated"}, format="json").status_code, 200)
        data = self.statement(c).data
        self.assertEqual(data["instalments"][0]["status"], "cancelled")
        self.assertEqual(data["totals"]["total"], "50.00")  # cancelled instalments leave every total
        self.assertEqual(self.client.post(f"/api/payments/instalments/{a.pk}/cancel/", {"reason": "again"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(f"/api/payments/instalments/{a.pk}/", {"amount": "9"}, format="json").status_code, 400)
        self.assertEqual(self.pay(a).data["detail"], services.MSG_STATE)
        self.pay(b, "10")
        self.assertEqual(self.client.post(f"/api/payments/instalments/{b.pk}/cancel/", {"reason": "x"}, format="json").data["detail"], services.MSG_CANCEL_PAID)
        self.assertTrue(Instalment.objects.get(pk=a.pk).cancelled_at)  # kept, never deleted

    def test_database_constraints(self):
        c = self.mk()
        for kwargs in ({"amount": Decimal("0")}, {"amount": Decimal("-1")}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Instalment.objects.create(client=c, number=1, due_date=TODAY(), created_by=self.head, **kwargs)
        Instalment.objects.create(client=c, number=1, due_date=TODAY(), amount=Decimal("5"), created_by=self.head)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Instalment.objects.create(client=c, number=1, due_date=TODAY(), amount=Decimal("5"), created_by=self.head)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Instalment.objects.create(client=c, number=2, due_date=TODAY(), amount=Decimal("5"), created_by=self.head, cancelled_at=timezone.now())


class PaymentTests(PCase):
    def test_statuses_are_computed(self):
        c, _ = self.schedule(rows=[{"due_date": D(10), "amount": "100"}, {"due_date": D(20), "amount": "100"}, {"due_date": D(30), "amount": "100"}, {"due_date": D(40), "amount": "100"}])
        a, b, d = self.inst(c, 0), self.inst(c, 1), self.inst(c, 2)
        self.pay(a, "100")
        self.pay(b, "30")
        self.assertEqual([r["status"] for r in self.statement(c).data["instalments"]], ["paid", "partially_paid", "expected", "expected"])
        Instalment.objects.filter(pk__in=[a.pk, b.pk, d.pk]).update(due_date=TODAY() - timedelta(days=3))
        self.assertEqual([r["status"] for r in self.statement(c).data["instalments"]], ["paid", "overdue", "overdue", "expected"])  # partial + past due = overdue
        row = self.row(c, 1) if False else next(r for r in self.statement(c).data["instalments"] if r["id"] == b.pk)
        self.assertEqual((row["paid"], row["balance"]), ("30.00", "70.00"))
        t = self.statement(c).data["totals"]
        self.assertEqual((t["total"], t["paid"], t["balance"], t["overdue_amount"], t["overdue_count"]), ("400.00", "130.00", "270.00", "170.00", 2))

    def test_due_today_is_not_overdue_until_tomorrow(self):
        c, _ = self.schedule(rows=[{"due_date": D(0), "amount": "10"}])
        self.assertEqual(self.row(c)["status"], "expected")
        Instalment.objects.update(due_date=TODAY() - timedelta(days=1))
        self.assertEqual(self.row(c)["status"], "overdue")

    def test_payment_validation(self):
        c, _ = self.schedule()
        i = self.inst(c)
        bad = [({"amount": "0"}, "amount"), ({"amount": "-1"}, "amount"), ({"amount": "x"}, "amount"), ({"amount": "100.01"}, "amount"),
               ({"received_on": D(1)}, "received_on"), ({"received_on": "nope"}, "received_on"), ({"received_on": D(-2000)}, "received_on"),
               ({"method": "barter"}, "method"), ({"reference": "r" * 101}, "reference")]
        for over, field in bad:
            res = self.pay(i, **over) if "amount" not in over else self.pay(i, over["amount"])
            self.assertEqual(res.status_code, 400, over)
            self.assertIn(field, res.data, over)
        self.assertEqual(Payment.objects.count(), 0)

    def test_cannot_overpay_even_in_pieces(self):
        c, _ = self.schedule()
        i = self.inst(c)
        self.assertEqual(self.pay(i, "60").status_code, 201)
        self.assertEqual(self.pay(i, "40").status_code, 201)
        self.assertEqual(self.pay(i, "0.01").data["amount"], services.MSG_PAY_OVER)
        self.assertEqual(self.row(c)["status"], "paid")

    def test_pay_audits_without_touching_other_clients(self):
        c, _ = self.schedule()
        i = self.inst(c)
        p = Payment.objects.get(pk=self.pay(i, "25.50", reference="TRX-1").data["recorded"])
        self.assertTrue(AuditEntry.objects.filter(content_type=content_type_for(Payment), object_id=p.pk, action="created", to_value="25.50 JOD").exists())
        self.assertTrue(AuditEntry.objects.filter(content_type=content_type_for(Instalment), object_id=i.pk, action="payment_recorded").exists())
        self.assertFalse(AuditEntry.objects.filter(content_type=content_type_for(Client)).exists())  # nothing leaks onto the client's own history

    def test_reversal_flow(self):
        c, _ = self.schedule()
        i = self.inst(c)
        p = Payment.objects.get(pk=self.pay(i, "100").data["recorded"])
        self.assertEqual(self.row(c)["status"], "paid")
        self.as_user(self.head)
        self.assertEqual(self.client.post(f"/api/payments/records/{p.pk}/reverse/", {"reason": " "}, format="json").data["reason"], services.MSG_REVERSAL_REASON)
        res = self.client.post(f"/api/payments/records/{p.pk}/reverse/", {"reason": "Bounced cheque"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(self.row(c)["status"], "expected")
        self.assertEqual(self.row(c)["paid"], "0.00")
        kinds = [(x["kind"], x["reversed"], x["can_reverse"]) for x in res.data["payments"]]
        self.assertEqual(sorted(kinds), [("payment", True, False), ("reversal", False, False)])
        self.assertEqual(Payment.objects.count(), 2)  # nothing deleted
        self.assertEqual(self.client.post(f"/api/payments/records/{p.pk}/reverse/", {"reason": "again"}, format="json").data["detail"], services.MSG_ALREADY_REVERSED)
        rev = Payment.objects.get(kind="reversal")
        self.assertEqual(self.client.post(f"/api/payments/records/{rev.pk}/reverse/", {"reason": "x"}, format="json").data["detail"], services.MSG_REVERSE_REVERSAL)
        self.assertEqual(self.pay(i, "100").status_code, 201)  # the balance is open again
        self.assertTrue(AuditEntry.objects.filter(content_type=content_type_for(Payment), object_id=p.pk, action="reversed", comment="Bounced cheque").exists())

    def test_ledger_rows_are_immutable(self):
        c, _ = self.schedule()
        p = Payment.objects.get(pk=self.pay(self.inst(c), "10").data["recorded"])
        p.amount = Decimal("99")
        with self.assertRaises(LedgerError):
            p.save()
        with self.assertRaises(LedgerError):
            p.delete()
        with self.assertRaises(LedgerError):
            Payment.objects.all().update(amount=1)
        with self.assertRaises(LedgerError):
            Payment.objects.all().delete()

    def test_database_blocks_malformed_payments(self):
        c, _ = self.schedule()
        i = self.inst(c)
        base = dict(instalment=i, received_on=TODAY(), recorded_by=self.head)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(amount=Decimal("0"), **base)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(amount=Decimal("5"), kind="reversal", reason="x", **base)  # a reversal must point at a payment
        p = Payment.objects.create(amount=Decimal("5"), **base)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(amount=Decimal("5"), kind="reversal", reverses=p, reason="", **base)  # and needs a reason
        Payment.objects.create(amount=Decimal("5"), kind="reversal", reverses=p, reason="ok", **base)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.create(amount=Decimal("5"), kind="reversal", reverses=p, reason="twice", **base)  # one reversal per payment


class OverviewAndStatementTests(PCase):
    def test_overview_rows_and_filters(self):
        a, _ = self.schedule(rows=[{"due_date": D(10), "amount": "100"}])
        b, _ = self.schedule(rows=[{"due_date": D(10), "amount": "50"}])
        c, _ = self.schedule(rows=[{"due_date": D(10), "amount": "20"}])
        self.pay(self.inst(c), "20")
        Instalment.objects.filter(client=b).update(due_date=TODAY() - timedelta(days=2))
        self.as_user(self.ceo)
        res = self.client.get("/api/payments/overview/")
        names = [r["company_name"] for r in res.data["results"]]
        self.assertEqual(names, [b.company_name, a.company_name, c.company_name])  # overdue first, then by balance
        first = res.data["results"][0]
        self.assertEqual((first["overdue_count"], first["overdue_amount"], first["balance"]), (1, "50.00", "50.00"))
        ids = lambda q: [r["client"] for r in self.client.get(f"/api/payments/overview/{q}").data["results"]]
        self.assertEqual(ids("?filter=overdue"), [b.pk])
        self.assertEqual(ids("?filter=settled"), [c.pk])
        self.assertEqual(set(ids("?filter=open")), {a.pk, b.pk})
        self.assertEqual(ids(f"?search={a.company_name}"), [a.pk])

    def test_list_cost_does_not_grow_with_clients(self):
        def cost():
            self.as_user(self.head)
            with CaptureQueriesContext(connection) as ctx:
                self.client.get("/api/payments/overview/")
            return len(ctx)

        self.schedule()
        few = cost()
        for _ in range(6):
            self.schedule()
        self.assertEqual(cost(), few)

    def test_statement_and_csv(self):
        c, _ = self.schedule(rows=[{"due_date": D(5), "amount": "100", "note": "=HYPERLINK(1)"}])
        self.pay(self.inst(c), "40", reference="+cmd")
        self.as_user(self.ceo)
        res = self.client.get(f"/api/payments/clients/{c.pk}/export/")
        self.assertEqual(res.status_code, 200)
        body = res.content.decode("utf-8-sig")
        self.assertIn("'=HYPERLINK(1)", body)  # formulas are neutralised
        self.assertIn("'+cmd", body)
        self.assertIn("balance 60.00", body)
        self.assertTrue(res["Content-Disposition"].startswith("attachment"))

    def test_statement_for_a_client_without_a_schedule(self):
        c = self.mk()
        data = self.statement(c).data
        self.assertEqual((data["instalments"], data["payments"], data["totals"]["total"]), ([], [], "0.00"))


class ReminderTests(PCase):
    def test_overdue_reminder_once_to_head_and_ceo_without_amounts(self):
        c, _ = self.schedule(rows=[{"due_date": D(1), "amount": "777.77"}])
        Instalment.objects.update(due_date=TODAY() - timedelta(days=1))
        self.assertEqual(services.overdue_reminders(), 2)
        self.assertEqual(services.overdue_reminders(), 0)
        notes = Notification.objects.filter(kind="payment_overdue")
        self.assertEqual({n.user_id for n in notes}, {self.head.pk, self.ceo.pk})
        self.assertFalse(any("777" in (n.title + n.body) for n in notes))

    def test_paid_instalments_do_not_nag(self):
        c, _ = self.schedule(rows=[{"due_date": D(1), "amount": "10"}])
        self.pay(self.inst(c), "10")
        Instalment.objects.update(due_date=TODAY() - timedelta(days=1))
        self.assertEqual(services.overdue_reminders(), 0)

    def test_my_work_is_the_heads_only(self):
        c, _ = self.schedule(rows=[{"due_date": D(1), "amount": "10"}])
        Instalment.objects.update(due_date=TODAY() - timedelta(days=1))
        got = {}
        for key in ALL_ROLES:
            self.as_role(key)
            got[key] = [i for i in self.client.get("/api/my-work/").data["items"] if i["kind"] == "payment_overdue"]
        self.assertEqual({k for k, v in got.items() if v}, {"commercial_head"})
