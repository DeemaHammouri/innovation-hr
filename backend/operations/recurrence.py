"""The recurrence rules for Operation tasks, as pure functions (no database writes), so every edge case is unit-testable.

A rule is (frequency, interval_days, start_date). Its k-th occurrence is always counted from the start date, never from the previous
one, so a rule that starts on the 31st does not drift to the 28th for good, and a yearly rule that starts on 29 February lands on
28 February in a common year and on 29 February again in the next leap year.

Each occurrence has a nominal date and a period:
  * the nominal date is the calendar date the rule produces;
  * the due date is the nominal date moved to the next working day when it falls on the weekend (Friday and Saturday) or on a public
    holiday from the company calendar;
  * the period identifies the stretch of time the task covers (the day, the week, the month, ...). A task exists once per
    (rule, rule version, period), whatever the due date was moved to, so running the generator again can never create it twice.
"""
import calendar
from datetime import date, timedelta

from django.conf import settings

FREQUENCIES = ("daily", "weekly", "biweekly", "monthly", "quarterly", "semiannual", "yearly", "custom")
MONTHS = {"monthly": 1, "quarterly": 3, "semiannual": 6, "yearly": 12}


def weekend_days():
    return set(getattr(settings, "WEEKEND_DAYS", (4, 5)))  # Friday and Saturday


def add_months(d, n):
    y, m = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def nominal(frequency, start, interval_days, k):
    """The k-th (0-based) date the rule produces."""
    if frequency == "daily":
        return start + timedelta(days=k)
    if frequency == "weekly":
        return start + timedelta(weeks=k)
    if frequency == "biweekly":
        return start + timedelta(weeks=2 * k)
    if frequency in MONTHS:
        return add_months(start, MONTHS[frequency] * k)
    return start + timedelta(days=(interval_days or 1) * k)


def is_working_day(d, holidays=frozenset()):
    return d.weekday() not in weekend_days() and d not in holidays


def next_working_day(d, holidays=frozenset()):
    """`d` itself when it is a working day, otherwise the next one. Gives up after a year of closed days (a broken calendar)."""
    for _ in range(366):
        if is_working_day(d, holidays):
            return d
        d += timedelta(days=1)
    return d


def due(frequency, start, interval_days, k, holidays=frozenset()):
    return next_working_day(nominal(frequency, start, interval_days, k), holidays)


def period(frequency, nominal_date, start=None):
    """The period a nominal date belongs to. Daily and the day-count rules are their own date; a weekly rule covers its week
    (counted from Monday), monthly the calendar month, quarterly the quarter, semi-annual the half year, yearly the year."""
    if frequency == "weekly":
        return nominal_date - timedelta(days=nominal_date.weekday())
    if frequency == "monthly":
        return nominal_date.replace(day=1)
    if frequency == "quarterly":
        return date(nominal_date.year, 3 * ((nominal_date.month - 1) // 3) + 1, 1)
    if frequency == "semiannual":
        return date(nominal_date.year, 1 if nominal_date.month <= 6 else 7, 1)
    if frequency == "yearly":
        return date(nominal_date.year, 1, 1)
    return nominal_date  # daily, every 2 weeks, every N days: each occurrence is its own period
