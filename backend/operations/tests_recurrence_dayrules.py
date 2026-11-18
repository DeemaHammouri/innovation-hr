"""Unit tests for the rule types of the brief: every working day, first/last working day, n-th weekday, the per-rule weekend policy.
Pure functions, no database. Weekend is Friday and Saturday. Expected dates were worked out from the calendar, not from the code."""
from datetime import date

from django.test import SimpleTestCase

from operations import recurrence as r

# Calendar facts used below: 1 Nov 2026 is a Sunday. 30 Nov Monday. 1 Dec Tuesday, 31 Dec Thursday. 1 Jan 2027 Friday, 31 Jan Sunday.
# 31 Oct 2026 is a Saturday (so the last working day of October is Thursday the 29th). 28 Feb 2027 is a Sunday.


class FirstAndLastWorkingDayTests(SimpleTestCase):
    def months(self, rule, start, n, frequency="monthly", holidays=frozenset()):
        return [r.nominal(frequency, start, None, k, rule, holidays=holidays) for k in range(n)]

    def test_first_working_day_of_each_month(self):
        # Nov 1 is a Sunday (working), Dec 1 a Tuesday, Jan 1 2027 a Friday and Jan 2 a Saturday (closed): Sunday the 3rd.
        self.assertEqual(self.months("first_workday", date(2026, 11, 1), 3), [date(2026, 11, 1), date(2026, 12, 1), date(2027, 1, 3)])

    def test_last_working_day_of_each_month(self):
        # Oct 31 is a Saturday and Oct 30 a Friday: Thursday the 29th. Nov 30 Monday. Dec 31 Thursday. Jan 31 2027 is a Sunday.
        self.assertEqual(self.months("last_workday", date(2026, 10, 1), 4), [date(2026, 10, 29), date(2026, 11, 30), date(2026, 12, 31), date(2027, 1, 31)])

    def test_a_public_holiday_is_not_a_working_day(self):
        holidays = frozenset({date(2026, 12, 1), date(2026, 12, 31)})
        self.assertEqual(r.nominal("monthly", date(2026, 12, 1), None, 0, "first_workday", holidays=holidays), date(2026, 12, 2))
        self.assertEqual(r.nominal("monthly", date(2026, 12, 1), None, 0, "last_workday", holidays=holidays), date(2026, 12, 30))

    def test_the_first_occurrence_never_falls_before_the_start_date(self):
        # Started on 18 Nov: the first working day of November has passed, so the rule begins in December.
        self.assertEqual(self.months("first_workday", date(2026, 11, 18), 2), [date(2026, 12, 1), date(2027, 1, 3)])
        # Started on 18 Nov: the last working day of November (the 30th) is still ahead, so it counts.
        self.assertEqual(self.months("last_workday", date(2026, 11, 18), 2), [date(2026, 11, 30), date(2026, 12, 31)])

    def test_quarterly_semiannual_and_yearly_use_the_same_day_rules(self):
        self.assertEqual(self.months("last_workday", date(2026, 10, 1), 3, "quarterly"), [date(2026, 10, 29), date(2027, 1, 31), date(2027, 4, 29)])
        self.assertEqual(self.months("first_workday", date(2026, 11, 1), 3, "semiannual"), [date(2026, 11, 1), date(2027, 5, 2), date(2027, 11, 1)])
        self.assertEqual(self.months("last_workday", date(2026, 10, 1), 2, "yearly"), [date(2026, 10, 29), date(2027, 10, 31)])  # 31 Oct 2027 is a Sunday: working

    def test_the_day_rule_date_is_the_old_behaviour(self):
        start = date(2026, 1, 31)
        self.assertEqual([r.nominal("monthly", start, None, k, "date") for k in range(3)], [r.nominal("monthly", start, None, k) for k in range(3)])
        self.assertEqual(r.nominal("monthly", start, None, 1, None), date(2026, 2, 28))


class NthWeekdayTests(SimpleTestCase):
    TUESDAY, THURSDAY, SUNDAY, MONDAY, FRIDAY = 1, 3, 6, 0, 4

    def nth(self, frequency, start, n, nth, weekday):
        return [r.nominal(frequency, start, None, k, "nth_weekday", nth, weekday) for k in range(n)]

    def test_second_tuesday(self):
        self.assertEqual(self.nth("monthly", date(2026, 11, 1), 3, 2, self.TUESDAY), [date(2026, 11, 10), date(2026, 12, 8), date(2027, 1, 12)])

    def test_last_thursday(self):
        self.assertEqual(self.nth("monthly", date(2026, 11, 1), 2, -1, self.THURSDAY), [date(2026, 11, 26), date(2026, 12, 31)])

    def test_first_sunday_and_fourth_monday(self):
        self.assertEqual(self.nth("monthly", date(2026, 12, 1), 1, 1, self.SUNDAY), [date(2026, 12, 6)])
        self.assertEqual(r.nominal("monthly", date(2027, 2, 1), None, 0, "nth_weekday", 4, self.MONDAY), date(2027, 2, 22))

    def test_last_monday_of_february_in_a_leap_year(self):
        self.assertEqual(r.nominal("yearly", date(2028, 2, 1), None, 0, "nth_weekday", -1, self.MONDAY), date(2028, 2, 28))

    def test_it_begins_with_the_next_month_when_this_months_day_has_passed(self):
        # Started on 18 Nov: the 2nd Tuesday of November was the 10th, so the first task is December's (the 8th).
        self.assertEqual(self.nth("monthly", date(2026, 11, 18), 2, 2, self.TUESDAY), [date(2026, 12, 8), date(2027, 1, 12)])

    def test_the_nth_weekday_is_always_inside_the_month(self):
        for month in range(1, 13):
            for weekday in range(7):
                for nth in (1, 2, 3, 4, -1):
                    d = r.month_day(2027, month, "nth_weekday", nth, weekday)
                    self.assertEqual((d.year, d.month, d.weekday()), (2027, month, weekday))

    def test_a_missing_weekday_or_a_bad_nth_is_an_error_not_a_wrong_date(self):
        with self.assertRaises(ValueError):
            r.month_day(2026, 11, "nth_weekday", 2, None)
        with self.assertRaises(ValueError):
            r.month_day(2026, 11, "nth_weekday", 5, 1)
        with self.assertRaises(ValueError):
            r.month_day(2026, 11, "no_such_rule")


class EveryWorkingDayTests(SimpleTestCase):
    def test_workdays_makes_a_task_for_each_working_day_and_none_for_the_weekend(self):
        start = date(2026, 11, 18)  # Wednesday
        made = [r.nominal("workdays", start, None, k) for k in range(7) if not r.skipped("workdays", "next", r.nominal("workdays", start, None, k))]
        self.assertEqual(made, [date(2026, 11, 18), date(2026, 11, 19), date(2026, 11, 22), date(2026, 11, 23), date(2026, 11, 24)])  # Fri 20 and Sat 21 skipped

    def test_workdays_skips_a_public_holiday_whatever_the_policy(self):
        holiday = frozenset({date(2026, 11, 19)})
        for policy in r.POLICIES:
            self.assertTrue(r.skipped("workdays", policy, date(2026, 11, 19), holiday), policy)

    def test_workdays_is_one_period_per_day(self):
        self.assertEqual(r.period("workdays", date(2026, 11, 19)), date(2026, 11, 19))


class WeekendPolicyTests(SimpleTestCase):
    FRIDAY, SATURDAY = date(2026, 11, 20), date(2026, 11, 21)

    def due(self, frequency, start, policy, holidays=frozenset(), k=0):
        return r.due(frequency, start, None, k, holidays, policy=policy)

    def test_next_moves_to_the_next_working_day(self):
        self.assertEqual(self.due("weekly", self.FRIDAY, "next"), date(2026, 11, 22))
        self.assertEqual(self.due("weekly", self.SATURDAY, "next"), date(2026, 11, 22))

    def test_previous_moves_to_the_previous_working_day(self):
        self.assertEqual(self.due("weekly", self.FRIDAY, "previous", k=1), date(2026, 11, 26))  # the 27th is a Friday: back to Thursday
        # 31 Oct 2026 is a Saturday and the rule starts there: going back to Thursday the 29th would be before the start, so it moves forward.
        self.assertEqual(r.due("monthly", date(2026, 10, 31), None, 0, frozenset(), policy="previous"), date(2026, 11, 1))

    def test_previous_never_goes_before_the_rules_own_start(self):
        # Starts on a Friday: going back to Thursday would be before the start, so the first task moves forward instead.
        self.assertEqual(self.due("weekly", self.FRIDAY, "previous"), date(2026, 11, 22))
        self.assertEqual(self.due("weekly", self.FRIDAY, "previous", k=1), date(2026, 11, 26))

    def test_previous_over_a_holiday_and_a_weekend(self):
        # Thursday 26 Nov is a holiday and 27/28 the weekend: a task on Saturday 28 Nov goes back to Wednesday 25 Nov.
        start = date(2026, 11, 14)  # a Saturday, weekly: 14, 21, 28
        self.assertEqual(self.due("weekly", start, "previous", frozenset({date(2026, 11, 26)}), k=2), date(2026, 11, 25))

    def test_keep_leaves_the_date_on_the_closed_day(self):
        self.assertEqual(self.due("weekly", self.FRIDAY, "keep"), self.FRIDAY)
        self.assertEqual(self.due("monthly", date(2026, 10, 31), "keep"), date(2026, 10, 31))  # a Saturday

    def test_skip_makes_no_task_and_does_not_move_it(self):
        self.assertTrue(r.skipped("weekly", "skip", self.FRIDAY))
        self.assertFalse(r.skipped("weekly", "skip", date(2026, 11, 22)))
        self.assertEqual(self.due("weekly", self.FRIDAY, "skip"), self.FRIDAY)

    def test_the_other_policies_never_skip_a_non_daily_rule(self):
        for policy in ("next", "previous", "keep"):
            self.assertFalse(r.skipped("weekly", policy, self.FRIDAY), policy)
            self.assertFalse(r.skipped("monthly", policy, self.SATURDAY), policy)

    def test_a_daily_rule_keeps_its_old_meaning_of_next(self):
        self.assertTrue(r.skipped("daily", "next", self.FRIDAY))  # as before: no task for a day nobody works
        self.assertTrue(r.skipped("daily", "skip", self.FRIDAY))
        self.assertFalse(r.skipped("daily", "keep", self.FRIDAY))
        self.assertFalse(r.skipped("daily", "previous", self.FRIDAY))

    def test_a_working_day_is_never_moved_or_skipped(self):
        d = date(2026, 11, 22)  # Sunday
        for policy in r.POLICIES:
            self.assertEqual(self.due("weekly", d, policy), d)
            self.assertFalse(r.skipped("weekly", policy, d))

    def test_a_public_holiday_is_treated_like_the_weekend(self):
        holiday = frozenset({date(2026, 11, 22)})  # a Sunday that is a holiday
        self.assertEqual(self.due("weekly", date(2026, 11, 22), "next", holiday), date(2026, 11, 23))
        self.assertTrue(r.skipped("weekly", "skip", date(2026, 11, 22), holiday))

    def test_the_policy_never_changes_the_period(self):
        # The period comes from the nominal date, so a task moved into the next month still belongs to the month it was meant for.
        self.assertEqual(r.period("monthly", date(2026, 10, 31)), date(2026, 10, 1))
        self.assertEqual(r.due("monthly", date(2026, 10, 31), None, 0, frozenset(), policy="next"), date(2026, 11, 1))


class LeapYearAndMonthEndWithDayRulesTests(SimpleTestCase):
    def test_month_end_clamping_is_unchanged_for_the_date_rule(self):
        self.assertEqual([r.nominal("monthly", date(2027, 1, 31), None, k, "date") for k in range(3)], [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31)])

    def test_last_working_day_in_february_of_a_leap_year(self):
        # 29 Feb 2028 is a Tuesday: working, so it is the last working day.
        self.assertEqual(r.nominal("yearly", date(2028, 2, 1), None, 0, "last_workday"), date(2028, 2, 29))
        # 28 Feb 2027 is a Sunday: working.
        self.assertEqual(r.nominal("yearly", date(2027, 2, 1), None, 0, "last_workday"), date(2027, 2, 28))

    def test_a_year_boundary_is_crossed_correctly(self):
        self.assertEqual(r.nominal("monthly", date(2026, 12, 1), None, 1, "last_workday"), date(2027, 1, 31))
        self.assertEqual(r.nominal("quarterly", date(2026, 11, 1), None, 2, "first_workday"), date(2027, 5, 2))
