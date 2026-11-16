"""Objective 12: the dashboard and the monthly target. Every number is compared with a count made straight from the database."""
from datetime import date, datetime, time, timedelta
from unittest import mock

from django.utils import timezone

from leads import insights
from leads.models import Lead, MonthlyTarget
from leads.tests import LeadCase


def local(d, hh=12, mm=0):
    return timezone.make_aware(datetime.combine(d, time(hh, mm)))


class InsightCase(LeadCase):
    def add(self, when, **over):
        lead = self.mk(**over)
        Lead.objects.filter(pk=lead.pk).update(created_at=when)
        return lead


class DashboardTests(InsightCase):
    def test_access(self):
        self.assert_matrix("get", "/api/leads/dashboard/", {"ceo": 200, "marketing": 200, "commercial_head": 200, "*": 403})

    def test_numbers_equal_a_manual_count(self):
        today = timezone.localdate()
        self.mk(created_by=self.mkt, source="Fair")
        self.add(local(today - timedelta(days=3)), source="Fair", status="contacted", first_contacted_at=timezone.now())
        self.add(local(today - timedelta(days=10)), source="Web", status="qualified", first_contacted_at=timezone.now())
        self.add(local(today - timedelta(days=40)), source="Web", status="waiting", next_follow_up=today - timedelta(days=1), first_contacted_at=timezone.now())
        self.mk(status="waiting", next_follow_up=today, first_contacted_at=timezone.now())
        archived = self.mk()
        Lead.objects.filter(pk=archived.pk).update(archived_at=timezone.now())
        self.as_user(self.head)
        d = self.client.get("/api/leads/dashboard/").data
        live = Lead.objects.filter(archived_at__isnull=True)
        self.assertEqual(d["total"], live.count(), "archived leads are left out")
        self.assertEqual(d["added"]["today"], sum(1 for x in live if timezone.localtime(x.created_at).date() == today))
        self.assertEqual(d["added"]["last_7_days"], sum(1 for x in live if today - timedelta(days=6) <= timezone.localtime(x.created_at).date() <= today))
        self.assertEqual(d["added"]["this_month"], sum(1 for x in live if timezone.localtime(x.created_at).date().replace(day=1) == today.replace(day=1)))
        contacted = sum(1 for x in live if x.first_contacted_at)
        self.assertEqual(d["contact_rate"], round(contacted / live.count() * 100, 1))
        self.assertEqual(d["acceptance_rate"], round(live.filter(status="qualified").count() / contacted * 100, 1))
        self.assertEqual(d["follow_ups"], {"due_today": 1, "overdue": 1})
        self.assertEqual({r["status"]: r["count"] for r in d["by_status"]}, {s: live.filter(status=s).count() for s in Lead.Status.values})
        self.assertEqual({r["source"]: r["count"] for r in d["by_source"]}, {"": 1, "Fair": 2, "Web": 2})
        self.assertEqual(sum(r["count"] for r in d["per_day"]), sum(1 for x in live if timezone.localtime(x.created_at).date() >= today - timedelta(days=29)))
        self.assertEqual(len(d["per_day"]), 30)
        self.assertEqual(d["top_contributors"][0], {"id": self.mkt.pk, "name": self.mkt.full_name, "count": live.filter(created_by=self.mkt).count()})

    def test_empty_database_has_no_division_errors(self):
        self.as_user(self.head)
        d = self.client.get("/api/leads/dashboard/").data
        self.assertEqual((d["total"], d["contact_rate"], d["acceptance_rate"]), (0, 0, 0))

    def test_a_member_only_counts_their_own_leads(self):
        self.mk(assigned=self.member)
        self.mk(assigned=self.member2)
        self.assertEqual(insights.dashboard(self.member)["total"], 1)

    def test_midnight_boundary_uses_the_company_time_zone_not_utc(self):
        # Asia/Amman is UTC+3: 23:30 on the 14th local is 20:30 UTC (still the 14th); 00:30 on the 15th local is 21:30 UTC on the 14th.
        day = date(2026, 11, 15)
        self.add(local(day - timedelta(days=1), 23, 30))
        self.add(local(day, 0, 30))
        self.add(local(day, 23, 59))
        d = insights.dashboard(self.head, today=day)
        self.assertEqual(d["added"]["today"], 2)
        self.assertEqual(d["added"]["last_7_days"], 3)
        first_of_next = insights.dashboard(self.head, today=date(2026, 12, 1))
        self.assertEqual(first_of_next["added"]["this_month"], 0)

    def test_overdue_link_filter_returns_exactly_the_overdue_leads(self):
        today = timezone.localdate()
        late = self.mk(status="waiting", next_follow_up=today - timedelta(days=2), assigned=self.member)
        self.mk(status="waiting", next_follow_up=today, assigned=self.member)
        self.mk(status="contacted", assigned=self.member)
        self.as_user(self.head)
        count = insights.dashboard(self.head)["follow_ups"]["overdue"]
        res = self.client.get("/api/leads/?overdue=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual([r["id"] for r in res.data["results"]], [late.pk])
        self.assertEqual(res.data["count"], count)


class TargetTests(InsightCase):
    def setUp(self):
        super().setUp()
        MonthlyTarget.objects.create(year=2026, month=11, target=60, set_by=self.head)

    def fill(self, per_day_counts):
        for day, n in per_day_counts.items():
            for _ in range(n):
                self.add(local(date(2026, 11, day)))

    def prog(self, today):
        return insights.progress(2026, 11, today=today)

    def test_mid_month_maths(self):
        self.fill({1: 5, 5: 10, 10: 5})
        p = self.prog(date(2026, 11, 10))
        self.assertEqual((p["added"], p["remaining"], p["percent"]), (20, 40, 33.3))
        self.assertEqual((p["days_in_month"], p["days_elapsed"], p["days_left"]), (30, 10, 20))
        self.assertEqual(p["expected_by_today"], 20.0)
        self.assertTrue(p["on_track"])  # exactly on the line counts as on track
        self.assertEqual(p["required_per_day"], 2.0)

    def test_behind_when_below_the_expected_line(self):
        self.fill({2: 5})
        p = self.prog(date(2026, 11, 10))
        self.assertFalse(p["on_track"])
        self.assertEqual(p["required_per_day"], 2.8)  # 55 remaining over 20 days left

    def test_first_day_and_last_day_boundaries(self):
        self.fill({1: 2, 30: 3})
        first = self.prog(date(2026, 11, 1))
        self.assertEqual((first["days_elapsed"], first["days_left"], first["added"], first["expected_by_today"]), (1, 29, 2, 2.0))
        last = self.prog(date(2026, 11, 30))
        self.assertEqual((last["days_elapsed"], last["days_left"], last["added"], last["remaining"]), (30, 0, 5, 55))
        self.assertEqual(last["required_per_day"], 55.0)
        self.assertEqual(last["expected_by_today"], 60.0)
        self.assertFalse(last["on_track"])

    def test_leads_created_in_the_last_local_minute_belong_to_the_last_day(self):
        self.add(local(date(2026, 11, 30), 23, 59))
        self.add(local(date(2026, 12, 1), 0, 1))
        self.assertEqual(self.prog(date(2026, 11, 30))["added"], 1)

    def test_target_met_and_overshoot(self):
        self.fill({3: 61})
        p = self.prog(date(2026, 11, 20))
        self.assertEqual((p["remaining"], p["on_track"]), (0, True))
        self.assertEqual(p["percent"], 101.7)

    def test_past_and_future_months(self):
        MonthlyTarget.objects.create(year=2026, month=10, target=10, set_by=self.head)
        self.add(local(date(2026, 10, 5)))
        past = insights.progress(2026, 10, today=date(2026, 11, 15))
        self.assertEqual((past["days_elapsed"], past["days_left"], past["added"], past["required_per_day"]), (31, 0, 1, None))
        future = insights.progress(2027, 1, today=date(2026, 11, 15))
        self.assertEqual((future["days_elapsed"], future["target"], future["on_track"]), (0, 0, None))

    def test_chart_has_one_point_per_day_and_sums_to_added(self):
        self.fill({1: 2, 4: 3})
        p = self.prog(date(2026, 11, 10))
        self.assertEqual(len(p["days"]), 30)
        self.assertEqual(sum(x["count"] or 0 for x in p["days"]), p["added"])
        self.assertEqual(p["days"][9]["total"], 5)
        self.assertIsNone(p["days"][10]["count"])  # the future has no bar
        self.assertEqual(p["days"][29]["plan"], 60.0)

    def test_archived_leads_do_not_count(self):
        lead = self.add(local(date(2026, 11, 2)))
        Lead.objects.filter(pk=lead.pk).update(archived_at=timezone.now())
        self.assertEqual(self.prog(date(2026, 11, 10))["added"], 0)

    def test_setting_the_target_by_api(self):
        self.as_user(self.head)
        res = self.client.put("/api/leads/target/", {"month": "2026-11", "target": 80}, format="json")
        self.assertEqual((res.status_code, res.data["target"], res.data["set_by"]), (200, 80, self.head.full_name))
        self.assertEqual(MonthlyTarget.objects.filter(year=2026, month=11).count(), 1)
        for bad in (0, -1, "x", 1.5, True, 100001):
            self.assertEqual(self.client.put("/api/leads/target/", {"month": "2026-11", "target": bad}, format="json").status_code, 400, bad)
        self.assertEqual(self.client.put("/api/leads/target/", {"month": "2026-13", "target": 5}, format="json").status_code, 400)

    def test_who_may_read_and_set(self):
        self.assert_matrix("get", "/api/leads/target/?month=2026-11", {"ceo": 200, "marketing": 200, "commercial_head": 200, "*": 403})
        self.assert_matrix("put", "/api/leads/target/", {"ceo": 200, "commercial_head": 200, "*": 403}, data={"month": "2026-11", "target": 70})

    def test_endpoint_defaults_to_the_current_month(self):
        self.as_user(self.head)
        with mock.patch("django.utils.timezone.localdate", return_value=date(2026, 11, 10)):
            res = self.client.get("/api/leads/target/")
        self.assertEqual((res.data["year"], res.data["month"], res.data["target"]), (2026, 11, 60))
