"""Objective 12: the dashboard and the monthly target. Every number is compared with a count made straight from the database."""
from datetime import date, datetime, time, timedelta
from unittest import mock

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from leads import insights
from leads.models import Lead, LeadTarget
from leads.tests import LeadCase
from notifications.models import Notification


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


class TargetCase(InsightCase):
    """A Marketing employee asked for 50 leads from 10 to 19 November 2026 (ten days, both ends included)."""

    A, B = date(2026, 11, 10), date(2026, 11, 19)

    def setUp(self):
        super().setUp()
        self.t = LeadTarget.objects.create(user=self.mkt, start_date=self.A, end_date=self.B, target=50, set_by=self.head)

    def fill(self, counts, by=None):
        for day, n in counts.items():
            for _ in range(n):
                self.add(local(date(2026, 11, day)), created_by=by or self.mkt)

    def extra_marketing(self, email):
        """Marketing normally holds one person; a second one is made by hand to prove targets never mix people up."""
        from accounts.models import User

        person = self.make_user(email, "Commercial", "member")
        User.objects.filter(pk=person.pk).update(role_ref=self.mkt.role_ref)
        person.refresh_from_db()
        return person

    def prog(self, today):
        return insights.progress(LeadTarget.objects.select_related("user", "set_by").get(pk=self.t.pk), today=today)


class TargetMathTests(TargetCase):
    def test_mid_range(self):
        self.fill({10: 5, 12: 5})
        p = self.prog(date(2026, 11, 14))
        self.assertEqual((p["added"], p["remaining"], p["percent"]), (10, 40, 20.0))
        self.assertEqual((p["days_in_range"], p["days_elapsed"], p["days_left"]), (10, 5, 5))
        self.assertEqual(p["expected_by_today"], 25.0)
        self.assertFalse(p["on_track"])
        self.assertEqual(p["required_per_day"], 8.0)
        self.assertEqual(p["state"], "active")

    def test_exactly_on_the_line_is_on_track(self):
        self.fill({10: 10, 12: 15})
        p = self.prog(date(2026, 11, 14))
        self.assertEqual((p["added"], p["expected_by_today"], p["on_track"]), (25, 25.0, True))

    def test_first_day(self):
        self.fill({10: 5})
        p = self.prog(self.A)
        self.assertEqual((p["days_elapsed"], p["days_left"], p["added"], p["remaining"]), (1, 9, 5, 45))
        self.assertEqual((p["expected_by_today"], p["on_track"], p["required_per_day"], p["state"]), (5.0, True, 5.0, "active"))

    def test_last_day(self):
        self.fill({10: 20, 19: 3})
        p = self.prog(self.B)
        self.assertEqual((p["days_elapsed"], p["days_left"], p["added"], p["remaining"]), (10, 0, 23, 27))
        self.assertEqual((p["expected_by_today"], p["on_track"], p["state"]), (50.0, False, "active"))
        self.assertEqual(p["required_per_day"], 27.0)  # nothing is left but today: what is missing has to happen today

    def test_before_the_range_nothing_has_happened(self):
        self.fill({10: 5})
        p = self.prog(self.A - timedelta(days=1))
        self.assertEqual((p["days_elapsed"], p["days_left"], p["added"], p["remaining"], p["percent"]), (0, 10, 0, 50, 0.0))
        self.assertEqual((p["expected_by_today"], p["on_track"], p["required_per_day"], p["state"]), (0.0, None, None, "upcoming"))

    def test_after_the_range_everything_has(self):
        self.fill({10: 5, 19: 5})
        p = self.prog(self.B + timedelta(days=1))
        self.assertEqual((p["days_elapsed"], p["days_left"], p["added"], p["expected_by_today"]), (10, 0, 10, 50.0))
        self.assertEqual((p["on_track"], p["required_per_day"], p["state"]), (False, None, "ended"))
        self.fill({20: 9})  # later leads never change a finished range
        self.assertEqual(self.prog(date(2026, 12, 25))["added"], 10)

    def test_local_midnight_decides_which_day_a_lead_belongs_to(self):
        self.add(local(self.A - timedelta(days=1), 23, 59))  # one minute before the first day
        self.add(local(self.A, 0, 0))  # the first minute of the first day
        self.add(local(self.B, 23, 59))  # the last minute of the last day
        self.add(local(self.B + timedelta(days=1), 0, 0))  # the first minute after
        self.assertEqual(self.prog(self.B + timedelta(days=1))["added"], 2)

    def test_only_that_employees_leads_count_and_archived_do_not(self):
        self.fill({11: 3})
        self.fill({11: 4}, by=self.head)
        gone = self.add(local(date(2026, 11, 12)))
        Lead.objects.filter(pk=gone.pk).update(archived_at=timezone.now())
        self.assertEqual(self.prog(self.B)["added"], 3)

    def test_one_day_range(self):
        one = LeadTarget.objects.create(user=self.mkt, start_date=date(2027, 1, 5), end_date=date(2027, 1, 5), target=4, set_by=self.head)
        p = insights.progress(one, today=date(2027, 1, 5))
        self.assertEqual((p["days_in_range"], p["days_elapsed"], p["days_left"], p["expected_by_today"], p["required_per_day"]), (1, 1, 0, 4.0, 4.0))

    def test_range_across_a_month_and_year_end(self):
        t = LeadTarget.objects.create(user=self.mkt, start_date=date(2026, 12, 28), end_date=date(2027, 1, 3), target=7, set_by=self.head)
        p = insights.progress(t, today=date(2026, 12, 31))
        self.assertEqual((p["days_in_range"], p["days_elapsed"], p["days_left"], p["expected_by_today"]), (7, 4, 3, 4.0))

    def test_target_met_and_overshoot(self):
        self.fill({11: 51})
        p = self.prog(date(2026, 11, 15))
        self.assertEqual((p["remaining"], p["on_track"], p["percent"], p["required_per_day"]), (0, True, 102.0, 0.0))

    def test_chart_has_one_point_per_day_and_sums_to_added(self):
        self.fill({10: 2, 13: 3})
        p = self.prog(date(2026, 11, 15))
        self.assertEqual(len(p["days"]), 10)
        self.assertEqual(sum(x["count"] or 0 for x in p["days"]), p["added"])
        self.assertEqual(p["days"][5]["total"], 5)
        self.assertIsNone(p["days"][6]["count"])
        self.assertEqual(p["days"][-1]["plan"], 50.0)

    def test_team_target_counts_everyones_leads(self):
        team = LeadTarget.objects.create(user=None, start_date=self.A, end_date=self.B, target=10, set_by=self.head)
        self.fill({11: 2})
        self.fill({11: 3}, by=self.head)
        self.assertEqual(insights.progress(team, today=self.B)["added"], 5)


class TargetApiTests(TargetCase):
    def body(self, **over):
        data = {"user": self.mkt.pk, "start_date": "2027-02-01", "end_date": "2027-02-10", "target": 30}
        data.update(over)
        return data

    def post(self, actor=None, **over):
        self.as_user(actor or self.head)
        return self.client.post("/api/leads/targets/", self.body(**over), format="json")

    def test_who_may_do_what(self):
        self.assert_matrix("get", "/api/leads/targets/", {"ceo": 200, "marketing": 200, "commercial_head": 200, "*": 403})
        self.assert_matrix("get", "/api/leads/targets/assignees/", {"ceo": 200, "commercial_head": 200, "*": 403})
        for key in ("ceo", "commercial_head"):
            LeadTarget.objects.filter(start_date__year=2027).delete()
            self.as_role(key)
            self.assertEqual(self.client.post("/api/leads/targets/", self.body(), format="json").status_code, 201, key)
        for key in ("marketing", "commercial_member", "hr_head"):
            self.as_role(key)
            self.assertEqual(self.client.post("/api/leads/targets/", self.body(start_date="2027-05-01", end_date="2027-05-02"), format="json").status_code, 403, key)
            self.assertEqual(self.client.patch(f"/api/leads/targets/{self.t.pk}/", {"target": 9}, format="json").status_code, 403, key)
            self.assertEqual(self.client.delete(f"/api/leads/targets/{self.t.pk}/").status_code, 403, key)

    def test_create_returns_progress_and_tells_the_employee_in_their_language(self):
        self.mkt.preferred_language = "ar"
        self.mkt.save()
        res = self.post()
        self.assertEqual((res.status_code, res.data["user_name"], res.data["state"], res.data["days_in_range"]), (201, self.mkt.full_name, "upcoming", 10))
        n = Notification.objects.get(user=self.mkt, kind="target_assigned")
        self.assertIn("هدفًا", n.title)

    def test_validation(self):
        bad = [
            dict(user=self.member.pk), dict(user=None), dict(user="x"),
            dict(start_date="nope"), dict(end_date=None), dict(end_date="2027-01-31"),
            dict(end_date="2028-12-31"), dict(target=0), dict(target=-3), dict(target="x"), dict(target=1.5), dict(target=True), dict(target=100001),
        ]
        for over in bad:
            self.assertEqual(self.post(**over).status_code, 400, over)
        self.assertEqual(LeadTarget.objects.filter(start_date__year=2027).count(), 0)

    def test_the_same_person_cannot_have_overlapping_ranges(self):
        self.assertEqual(self.post().status_code, 201)
        self.assertEqual(self.post(start_date="2027-02-10", end_date="2027-02-12").status_code, 400)  # shares a day
        self.assertEqual(self.post(start_date="2027-02-11", end_date="2027-02-12").status_code, 201)  # next day is fine
        other = self.extra_marketing("mkt2@x.com")
        self.assertEqual(self.post(user=other.pk).status_code, 201)  # another person can overlap

    def test_a_marketing_employee_sees_only_their_own_targets(self):
        other = self.extra_marketing("mkt3@x.com")
        LeadTarget.objects.create(user=other, start_date=self.A, end_date=self.B, target=5, set_by=self.head)
        self.as_user(self.mkt)
        rows = self.client.get("/api/leads/targets/?all=1").data
        self.assertEqual([r["user"] for r in rows], [self.mkt.pk])
        theirs = LeadTarget.objects.get(user=other)
        self.assertEqual(self.client.get(f"/api/leads/targets/{theirs.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/leads/targets/{self.t.pk}/").status_code, 200)
        self.as_user(self.head)
        self.assertEqual(len(self.client.get("/api/leads/targets/?all=1").data), 2)
        self.assertEqual(len(self.client.get(f"/api/leads/targets/?all=1&user={other.pk}").data), 1)

    def test_ended_targets_are_hidden_unless_asked_for(self):
        old = LeadTarget.objects.create(user=self.mkt, start_date=date(2020, 1, 1), end_date=date(2020, 1, 31), target=3, set_by=self.head)
        self.as_user(self.head)
        self.assertNotIn(old.pk, [r["id"] for r in self.client.get("/api/leads/targets/").data])
        self.assertIn(old.pk, [r["id"] for r in self.client.get("/api/leads/targets/?all=1").data])

    def test_change_and_remove_leave_an_audit_line(self):
        self.as_user(self.head)
        res = self.client.patch(f"/api/leads/targets/{self.t.pk}/", {"target": 80, "end_date": "2026-11-25"}, format="json")
        self.assertEqual((res.status_code, res.data["target"], res.data["end_date"]), (200, 80, "2026-11-25"))
        self.assertEqual(self.client.patch(f"/api/leads/targets/{self.t.pk}/", {"end_date": "2026-11-01"}, format="json").status_code, 400)
        pk = self.t.pk
        self.assertEqual(self.client.delete(f"/api/leads/targets/{pk}/").status_code, 204)
        self.assertFalse(LeadTarget.objects.filter(pk=pk).exists())
        from audit.models import AuditEntry

        self.assertEqual(list(AuditEntry.objects.filter(action__startswith="target_").order_by("id").values_list("action", flat=True)), ["target_changed", "target_removed"])

    def test_assignees_are_the_active_marketing_people(self):
        self.as_user(self.head)
        ids = [r["id"] for r in self.client.get("/api/leads/targets/assignees/").data]
        self.assertIn(self.mkt.pk, ids)
        self.assertNotIn(self.member.pk, ids)


class MonthlyTargetMigrationTests(TransactionTestCase):
    """The old company-wide monthly targets survive as dated targets."""

    def run_forward(self, marketing_users):
        executor = MigrationExecutor(connection)
        before = [("leads", "0010_lead_target"), ("accounts", "0008_sync_new_capabilities")]
        executor.migrate(before)
        apps = executor.loader.project_state(before).apps
        User, Monthly = apps.get_model("accounts", "User"), apps.get_model("leads", "MonthlyTarget")
        Role = apps.get_model("accounts", "Role")
        role = Role.objects.create(key="marketing", name_en="Marketing", name_ar="التسويق", is_head=False)
        boss = User.objects.create(email="boss@x.com", full_name="Boss", password="x")
        for i in range(marketing_users):
            User.objects.create(email=f"m{i}@x.com", full_name=f"M{i}", password="x", role_ref=role)
        Monthly.objects.create(year=2026, month=2, target=40, set_by=boss)
        Monthly.objects.create(year=2026, month=11, target=60, set_by=boss)
        executor = MigrationExecutor(connection)
        executor.migrate([("leads", "0012_drop_monthly_target")])
        return executor.loader.project_state([("leads", "0012_drop_monthly_target")]).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_each_month_becomes_a_range_for_the_only_marketing_user(self):
        apps = self.run_forward(1)
        rows = {(t.start_date.isoformat(), t.end_date.isoformat()): t for t in apps.get_model("leads", "LeadTarget").objects.all()}
        self.assertEqual(set(rows), {("2026-02-01", "2026-02-28"), ("2026-11-01", "2026-11-30")})
        self.assertEqual({t.user.full_name for t in rows.values()}, {"M0"})
        self.assertEqual(rows[("2026-11-01", "2026-11-30")].target, 60)

    def test_with_two_marketing_users_the_target_stays_a_team_target(self):
        apps = self.run_forward(2)
        self.assertEqual({t.user_id for t in apps.get_model("leads", "LeadTarget").objects.all()}, {None})

    def test_with_no_marketing_user_nothing_is_lost(self):
        apps = self.run_forward(0)
        self.assertEqual(apps.get_model("leads", "LeadTarget").objects.count(), 2)
