"""Unit tests for the recurrence rules: month-end, leap year, weekend and holiday handling. No database."""
from datetime import date

from django.test import SimpleTestCase

from operations import recurrence as r


class MonthEndTests(SimpleTestCase):
    def test_monthly_from_the_31st_clamps_and_comes_back(self):
        start = date(2026, 1, 31)
        got = [r.nominal("monthly", start, None, k) for k in range(5)]
        self.assertEqual(got, [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30), date(2026, 5, 31)])

    def test_monthly_in_a_leap_year_uses_the_29th(self):
        self.assertEqual(r.nominal("monthly", date(2028, 1, 31), None, 1), date(2028, 2, 29))

    def test_quarterly_and_semiannual_from_the_end_of_a_month(self):
        self.assertEqual([r.nominal("quarterly", date(2026, 11, 30), None, k) for k in range(3)], [date(2026, 11, 30), date(2027, 2, 28), date(2027, 5, 30)])
        self.assertEqual([r.nominal("semiannual", date(2026, 8, 31), None, k) for k in range(3)], [date(2026, 8, 31), date(2027, 2, 28), date(2027, 8, 31)])


class LeapYearTests(SimpleTestCase):
    def test_yearly_from_29_february(self):
        start = date(2028, 2, 29)
        got = [r.nominal("yearly", start, None, k) for k in range(5)]
        self.assertEqual(got, [date(2028, 2, 29), date(2029, 2, 28), date(2030, 2, 28), date(2031, 2, 28), date(2032, 2, 29)])

    def test_daily_crosses_29_february(self):
        self.assertEqual([r.nominal("daily", date(2028, 2, 28), None, k) for k in range(3)], [date(2028, 2, 28), date(2028, 2, 29), date(2028, 3, 1)])


class OtherRulesTests(SimpleTestCase):
    def test_weekly_biweekly_and_custom_count_from_the_start(self):
        start = date(2026, 11, 2)
        self.assertEqual(r.nominal("weekly", start, None, 2), date(2026, 11, 16))
        self.assertEqual(r.nominal("biweekly", start, None, 2), date(2026, 11, 30))
        self.assertEqual(r.nominal("custom", start, 45, 2), date(2027, 1, 31))

    def test_every_rule_type_is_known(self):
        self.assertEqual(set(r.FREQUENCIES), {"daily", "weekly", "biweekly", "monthly", "quarterly", "semiannual", "yearly", "custom"})


class WeekendAndHolidayTests(SimpleTestCase):
    def test_friday_and_saturday_are_the_weekend(self):
        self.assertEqual(r.weekend_days(), {4, 5})
        self.assertFalse(r.is_working_day(date(2026, 11, 20)))  # Friday
        self.assertFalse(r.is_working_day(date(2026, 11, 21)))  # Saturday
        self.assertTrue(r.is_working_day(date(2026, 11, 22)))  # Sunday
        self.assertTrue(r.is_working_day(date(2026, 11, 19)))  # Thursday

    def test_a_due_date_on_the_weekend_moves_to_sunday(self):
        self.assertEqual(r.due("monthly", date(2026, 11, 20), None, 0), date(2026, 11, 22))
        self.assertEqual(r.due("monthly", date(2026, 11, 21), None, 0), date(2026, 11, 22))

    def test_a_holiday_moves_the_date_and_a_holiday_before_the_weekend_chains(self):
        holidays = frozenset({date(2026, 11, 19), date(2026, 11, 22)})  # Thursday and the Sunday after the weekend
        self.assertEqual(r.due("monthly", date(2026, 11, 19), None, 0, holidays), date(2026, 11, 23))

    def test_the_period_does_not_change_when_the_date_moves(self):
        nominal = date(2026, 11, 21)
        self.assertEqual(r.period("monthly", nominal), date(2026, 11, 1))
        self.assertEqual(r.due("monthly", nominal, None, 0).month, 11)

    def test_a_calendar_that_closes_every_day_cannot_loop_forever(self):
        everything = frozenset(date(2026, 1, 1).fromordinal(date(2026, 1, 1).toordinal() + i) for i in range(400))
        self.assertIsInstance(r.next_working_day(date(2026, 1, 1), everything), date)


class PeriodTests(SimpleTestCase):
    def test_periods(self):
        self.assertEqual(r.period("daily", date(2026, 11, 18)), date(2026, 11, 18))
        self.assertEqual(r.period("weekly", date(2026, 11, 18)), date(2026, 11, 16))  # the Monday
        self.assertEqual(r.period("monthly", date(2026, 11, 18)), date(2026, 11, 1))
        self.assertEqual(r.period("quarterly", date(2026, 11, 18)), date(2026, 10, 1))
        self.assertEqual(r.period("semiannual", date(2026, 3, 18)), date(2026, 1, 1))
        self.assertEqual(r.period("semiannual", date(2026, 9, 18)), date(2026, 7, 1))
        self.assertEqual(r.period("yearly", date(2026, 11, 18)), date(2026, 1, 1))
