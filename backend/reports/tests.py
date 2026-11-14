from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from clients.models import Client
from core.roles import ALL_ROLES
from core.testing import RoleCase
from hr.models import EmployeeSalary
from leads.models import Lead
from lookups.models import RejectionReason
from payments import services as pay
from quotations.models import Quotation, QuotationVersion

TODAY = lambda: timezone.localdate()


class RCase(RoleCase):
    n = 0

    def setUp(self):
        super().setUp()
        self.reason = RejectionReason.objects.filter(is_active=True).first()

    def lead(self, status="new", assigned=None, company_name=None, **kw):
        RCase.n += 1
        return Lead.objects.create(
            ref=f"LD-7{RCase.n:03d}", company_name=company_name or f"Acme {RCase.n}", phone=f"07700000{RCase.n:02d}", created_by=self.users["marketing"],
            status=status, assigned_to=assigned or self.users["commercial_member"], assigned_at=timezone.now(), **kw,
        )

    def quote(self, status, total="100.00", currency="JOD", sent=False, lead=None):
        RCase.n += 1
        q = Quotation.objects.create(ref=f"QT-7{RCase.n:03d}", lead=lead or self.lead(status="qualified"), requested_by=self.users["commercial_member"], status=status,
                                     sent_at=timezone.now() if sent else None, outcome_at=timezone.now() if status in ("confirmed", "rejected") else None,
                                     rejection_reason=self.reason if status == "rejected" else None)
        QuotationVersion.objects.create(quotation=q, number=1, currency=currency, total=Decimal(total), created_by=self.users["commercial_member"])
        return q


class ReportAccessTests(RCase):
    def test_matrix_per_section(self):
        allowed = {"funnel": {"ceo", "commercial_head", "marketing"}, "revenue": {"ceo", "commercial_head"}, "forecast": {"ceo", "commercial_head"},
                   "operations": {"ceo", "operation_head"}, "hr": {"ceo", "hr_head"}}
        for section, roles in allowed.items():
            self.assert_matrix("get", f"/api/reports/{section}/", {**{r: 200 for r in roles}, "*": 403})
            self.assert_matrix("get", f"/api/reports/{section}/export/", {**{r: 200 for r in roles}, "*": 403})

    def test_unknown_section_and_anonymous(self):
        self.as_role("ceo")
        self.assertEqual(self.client.get("/api/reports/nope/").status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/reports/funnel/").status_code, 401)

    def test_index_lists_only_openable(self):
        for role, expected in (("ceo", 5), ("commercial_head", 3), ("hr_member", 0), ("operation_head", 1)):
            self.as_role(role)
            self.assertEqual(len(self.client.get("/api/reports/").data["sections"]), expected, role)

    def test_bad_period_refused(self):
        self.as_role("ceo")
        for qs in ("from=abc", "from=2026-05-01&to=2026-04-01", "from=2020-01-01&to=2026-01-01"):
            self.assertEqual(self.client.get(f"/api/reports/funnel/?{qs}").status_code, 400, qs)


def series_of(res, key):
    return next(s for s in res.data["series"] if s["key"] == key)


def val(s, key):
    return next(p for p in s["points"] if p["key"] == key)


class FunnelTests(RCase):
    def test_counts_conversions_and_durations(self):
        now = timezone.now() + timedelta(hours=1)  # after the leads were assigned, so the durations are positive
        a = self.lead("qualified", first_contacted_at=now, qualified_at=now)
        self.lead("contacted", first_contacted_at=now)
        self.lead("new")
        self.lead("rejected", rejection_reason=self.reason, rejected_at=now)
        self.as_role("commercial_head")
        res = self.client.get("/api/reports/funnel/")
        funnel = series_of(res, "funnel")
        self.assertEqual([(p["key"], p["value"]) for p in funnel["points"]][:3], [("created", 4), ("contacted", 2), ("qualified", 1)])
        conv = series_of(res, "conversions")
        self.assertEqual(val(conv, "created_to_contacted")["value"], 50.0)
        self.assertEqual(val(conv, "created_to_contacted")["n"], 4)
        self.assertEqual(sum(p["value"] for p in series_of(res, "lead_rejections")["points"]), 1)
        self.assertIsNotNone(val(series_of(res, "stage_hours"), "assigned_to_contact")["value"])
        self.assertEqual(val(series_of(res, "stage_hours"), "assigned_to_contact")["n"], 2)
        self.assertEqual(res.data["records"], 4)
        del a

    def test_empty_period_has_no_invented_numbers(self):
        self.as_role("ceo")
        res = self.client.get("/api/reports/funnel/")
        self.assertIsNone(val(series_of(res, "conversions"), "created_to_contacted")["value"])
        self.assertIsNone(val(series_of(res, "stage_hours"), "assigned_to_contact")["value"])

    def test_marketing_sees_only_own_leads_and_no_quotation_series(self):
        other = self.make_user("m2@x.com", "Marketing") if False else None
        self.lead("new")
        Lead.objects.create(ref="LD-7999", company_name="Not mine", created_by=self.users["commercial_head"], status="new")
        self.as_role("marketing")
        res = self.client.get("/api/reports/funnel/")
        self.assertEqual(val(series_of(res, "funnel"), "created")["value"], 1)
        self.assertNotIn("quotations", [s["key"] for s in res.data["series"]])
        self.assertNotIn("contract_signed", [p["key"] for p in series_of(res, "funnel")["points"]])
        del other

    def test_sla_breaches_counted(self):
        old = timezone.now() - timedelta(days=30)
        lead = self.lead("new")
        Lead.objects.filter(pk=lead.pk).update(assigned_at=old)
        self.as_role("ceo")
        res = self.client.get("/api/reports/funnel/")
        self.assertEqual(val(series_of(res, "sla_breaches"), "first_contact_overdue")["value"], 1)

    def test_csv_matches_and_is_safe(self):
        self.lead("new")
        self.as_role("ceo")
        res = self.client.get("/api/reports/funnel/export/")
        self.assertEqual(res["Content-Type"], "text/csv; charset=utf-8")
        text = res.content.decode("utf-8-sig")
        self.assertIn("funnel,funnel,created,1,count,", text)

    def test_query_count_does_not_grow_with_data(self):
        self.as_role("ceo")
        self.lead("qualified")
        self.client.get("/api/reports/funnel/")
        with CaptureQueriesContext(connection) as small:
            self.client.get("/api/reports/funnel/")
        for _ in range(15):
            self.quote("sent", sent=True)
        with CaptureQueriesContext(connection) as big:
            self.client.get("/api/reports/funnel/")
        self.assertLessEqual(len(big), len(small) + 2)


class ForecastTests(RCase):
    def history(self, confirmed, rejected, dropped):
        for _ in range(confirmed):
            self.quote("confirmed", sent=True)
        for _ in range(rejected):
            self.quote("rejected", sent=True)
        for _ in range(dropped):
            self.quote("cancelled")

    def test_refuses_when_too_thin(self):
        self.history(3, 2, 0)
        self.quote("sent", "5000.00", sent=True)
        self.as_role("commercial_head")
        res = self.client.get("/api/reports/forecast/")
        self.assertTrue(res.data["refused"])
        self.assertEqual(res.data["method"]["decided"], 5)
        self.assertEqual([s for s in res.data["series"] if s["key"].startswith("pipeline")], [])

    def test_computes_from_history(self):
        self.history(6, 6, 4)  # decided 12, confirmed 6 -> 0.5; with the open sent one, 13 of 17 left early reached the client
        self.quote("sent", "1000.00", sent=True)
        self.quote("in_review", "1000.00")
        self.as_role("commercial_head")
        res = self.client.get("/api/reports/forecast/")
        self.assertFalse(res.data["refused"])
        self.assertEqual(res.data["method"]["p_confirmed"], 0.5)
        self.assertAlmostEqual(res.data["method"]["p_sent"], 13 / 17, places=3)
        pipe = series_of(res, "pipeline_JOD")
        self.assertEqual(val(pipe, "open_value")["value"], 2000.0)
        self.assertAlmostEqual(val(pipe, "expected")["value"], 500.0 + 1000 * 0.5 * 13 / 17, places=1)
        self.assertEqual(val(pipe, "open_value")["n"], 2)

    def test_unpaid_instalments_shown_even_when_refused(self):
        client = Client.objects.create(company_name="Payer", created_by=self.users["ceo"])
        d = lambda n: (TODAY() + timedelta(days=n)).isoformat()
        pay.create_schedule(self.users["commercial_head"], client, {"currency": "JOD", "instalments": [{"due_date": d(-5), "amount": "300.00"}, {"due_date": d(40), "amount": "200.00"}]})
        self.as_role("ceo")
        res = self.client.get("/api/reports/forecast/")
        self.assertTrue(res.data["refused"])
        unpaid = series_of(res, "unpaid_JOD")
        self.assertEqual(val(unpaid, "overdue")["value"], 300.0)
        self.assertEqual(res.data["unpaid_records"], 2)


class RevenueTests(RCase):
    def test_expected_received_and_overdue(self):
        client = Client.objects.create(company_name="Payer", created_by=self.users["ceo"])
        d = lambda n: (TODAY() + timedelta(days=n)).isoformat()
        pay.create_schedule(self.users["commercial_head"], client, {"currency": "JOD", "instalments": [{"due_date": d(-3), "amount": "500.00"}, {"due_date": d(5), "amount": "500.00"}]})
        first = client.instalments.order_by("number").first()
        pay.record_payment(self.users["commercial_head"], first, {"amount": "200.00", "received_on": TODAY().isoformat(), "method": "cash"})
        self.as_role("commercial_head")
        res = self.client.get(f"/api/reports/revenue/?from={d(-30)}&to={d(30)}")
        exp = sum(p["value"] for p in series_of(res, "expected_JOD")["points"])
        rec = sum(p["value"] for p in series_of(res, "received_JOD")["points"])
        self.assertEqual((exp, rec), (1000.0, 200.0))
        self.assertEqual(res.data["kpis"]["JOD"], {"overdue_total": 300.0, "overdue_instalments": 1})
        self.assertEqual(series_of(res, "overdue_JOD")["points"][0]["label_en"], "Payer")


class OpsAndHrTests(RCase):
    def test_operations_and_hr_reports_have_no_salary_data(self):
        EmployeeSalary.objects.create(user=self.users["hr_member"], base_salary=Decimal("1234.56"), currency="JOD", updated_by=self.users["hr_head"])
        for role, section in (("ceo", "operations"), ("ceo", "hr"), ("hr_head", "hr"), ("operation_head", "operations")):
            self.as_role(role)
            res = self.client.get(f"/api/reports/{section}/")
            self.assertEqual(res.status_code, 200)
            self.assertNotIn("1234", str(res.data))
            self.assertNotIn("salary", str(res.data).lower())

    def test_hr_headcount(self):
        self.as_role("hr_head")
        res = self.client.get("/api/reports/hr/")
        self.assertEqual(val(series_of(res, "headcount"), "people")["value"], len(ALL_ROLES))


class SearchTests(RCase):
    def test_visibility_follows_each_module(self):
        mine = self.lead("qualified", company_name="Zeta Mine")
        other = self.make_user("cm2@x.com", "Commercial")
        self.lead("qualified", assigned=other, company_name="Zeta Theirs")
        self.quote("sent", sent=True, lead=mine)
        self.as_role("commercial_member")
        titles = [r["title"] for r in self.client.get("/api/search/?q=zeta").data["results"]]
        self.assertIn("Zeta Mine", titles)
        self.assertNotIn("Zeta Theirs", titles)
        self.as_role("commercial_head")
        titles = [r["title"] for r in self.client.get("/api/search/?q=zeta").data["results"]]
        self.assertIn("Zeta Theirs", titles)
        self.as_role("hr_member")
        kinds = {r["kind"] for r in self.client.get("/api/search/?q=zeta").data["results"]}
        self.assertEqual(kinds, {"quotation"})
        self.as_role("operation_member")
        self.assertEqual(self.client.get("/api/search/?q=zeta").data["results"], [])

    def test_short_query_and_anonymous(self):
        self.as_role("ceo")
        self.assertEqual(self.client.get("/api/search/?q=a").data["results"], [])
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/search/?q=abc").status_code, 401)

    def test_never_returns_salary_or_people(self):
        EmployeeSalary.objects.create(user=self.users["hr_member"], base_salary=Decimal("4321.00"), currency="JOD", updated_by=self.users["hr_head"])
        for role in ALL_ROLES:
            self.as_role(role)
            for q in ("4321", "salary", "hr member", "hr_member"):
                self.assertEqual(self.client.get(f"/api/search/?q={q}").data["results"], [], f"{role} {q}")

    def test_search_query_count_is_flat(self):
        for _ in range(3):
            self.lead("qualified", company_name="Flat Co")
        self.as_role("ceo")
        with CaptureQueriesContext(connection) as small:
            self.client.get("/api/search/?q=flat")
        for _ in range(10):
            self.lead("qualified", company_name="Flat Co")
        with CaptureQueriesContext(connection) as big:
            self.client.get("/api/search/?q=flat")
        self.assertEqual(len(small), len(big))
