"""The recurrence rules for Operation tasks, as pure functions (no database writes), so every edge case is unit-testable.

A rule is (frequency, interval_days, start_date) plus, for the month-based frequencies, a day rule, and for every rule a weekend policy.
Its k-th occurrence is always counted from the start date, never from the previous
one, so a rule that starts on the 31st does not drift to the 28th for good, and a yearly rule that starts on 29 February lands on
28 February in a common year and on 29 February again in the next leap year.

Each occurrence has a nominal date and a period:
  * the nominal date is the calendar date the rule produces;
  * the due date is the nominal date moved by the weekend policy when it falls on the weekend (Friday and Saturday) or on a public
    holiday from the company calendar: `next` moves it to the next working day (the default), `previous` to the previous one, `keep`
    leaves it where it is, `skip` makes no task for that occurrence. A daily rule has no use for `next` (two days would pile onto one),
    so there it means `skip`, and "workdays" (every working day) always skips closed days;
  * the period identifies the stretch of time the task covers (the day, the week, the month, ...). A task exists once per
    (rule, rule version, period), whatever the due date was moved to, so running the generator again can never create it twice.

Month-based rules (monthly, quarterly, semi-annual, yearly) can land on a day rule instead of the start date's day: the first or last
working day of the month, or the n-th weekday ("the 2nd Tuesday", "the last Thursday").
"""
import calendar
from datetime import date, timedelta

from django.conf import settings

FREQUENCIES = ("daily", "workdays", "weekly", "biweekly", "monthly", "quarterly", "semiannual", "yearly", "custom")
MONTHS = {"monthly": 1, "quarterly": 3, "semiannual": 6, "yearly": 12}
# Which day of the month a month-based rule lands on: the start date's day, the first or last working day, or "the 2nd Tuesday".
DAY_RULES = ("date", "first_workday", "last_workday", "nth_weekday")
NTH = (1, 2, 3, 4, -1)  # -1 is the last one
POLICIES = ("next", "previous", "keep", "skip")


def weekend_days():
    return set(getattr(settings, "WEEKEND_DAYS", (4, 5)))  # Friday and Saturday


def add_months(d, n):
    y, m = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def is_working_day(d, holidays=frozenset()):
    return d.weekday() not in weekend_days() and d not in holidays


def next_working_day(d, holidays=frozenset()):
    """`d` itself when it is a working day, otherwise the next one. Gives up after a year of closed days (a broken calendar)."""
    for _ in range(366):
        if is_working_day(d, holidays):
            return d
        d += timedelta(days=1)
    return d


def previous_working_day(d, holidays=frozenset()):
    """`d` itself when it is a working day, otherwise the one before it."""
    for _ in range(366):
        if is_working_day(d, holidays):
            return d
        d -= timedelta(days=1)
    return d


def month_day(year, month, day_rule, nth=None, weekday=None, holidays=frozenset()):
    """The date in (year, month) that a day rule names. first_workday and last_workday stay inside the month."""
    last = calendar.monthrange(year, month)[1]
    if day_rule == "first_workday":
        for day in range(1, last + 1):
            if is_working_day(date(year, month, day), holidays):
                return date(year, month, day)
        return date(year, month, 1)
    if day_rule == "last_workday":
        for day in range(last, 0, -1):
            if is_working_day(date(year, month, day), holidays):
                return date(year, month, day)
        return date(year, month, last)
    if day_rule == "nth_weekday":
        if weekday is None or nth not in NTH:
            raise ValueError("nth_weekday needs a weekday (0 Monday to 6 Sunday) and nth 1, 2, 3, 4 or -1")
        if nth == -1:
            back = (date(year, month, last).weekday() - weekday) % 7
            return date(year, month, last - back)
        ahead = (weekday - date(year, month, 1).weekday()) % 7
        return date(year, month, 1 + ahead + 7 * (nth - 1))  # 1 + 6 + 21 = 28 at most: always inside the month
    raise ValueError(f"unknown day rule {day_rule!r}")


def nominal(frequency, start, interval_days, k, day_rule="date", nth=None, weekday=None, holidays=frozenset()):
    """The k-th (0-based) date the rule produces.

    With a day rule other than "date" (month-based frequencies only) the k-th occurrence is that rule's day in the k-th month step from
    the start date's month; if the first one would fall before the start date, the rule begins with the next step instead."""
    if frequency in ("daily", "workdays"):
        return start + timedelta(days=k)
    if frequency == "weekly":
        return start + timedelta(weeks=k)
    if frequency == "biweekly":
        return start + timedelta(weeks=2 * k)
    if frequency in MONTHS:
        if day_rule in ("date", None):
            return add_months(start, MONTHS[frequency] * k)
        first = month_day(start.year, start.month, day_rule, nth, weekday, holidays)
        index = k + (1 if first < start else 0)
        anchor = add_months(start.replace(day=1), MONTHS[frequency] * index)
        return month_day(anchor.year, anchor.month, day_rule, nth, weekday, holidays)
    return start + timedelta(days=(interval_days or 1) * k)


def skipped(frequency, policy, nominal_date, holidays=frozenset()):
    """True when this occurrence makes no task: it falls on a closed day and the rule does not move it."""
    if is_working_day(nominal_date, holidays):
        return False
    if frequency == "workdays":
        return True
    if frequency == "daily":
        return policy in ("next", "skip", None)  # "move to the next working day" would pile two days onto one
    return policy == "skip"


def due(frequency, start, interval_days, k, holidays=frozenset(), day_rule="date", nth=None, weekday=None, policy="next"):
    """The date the k-th task is due: the nominal date, moved (or not) by the weekend policy."""
    d = nominal(frequency, start, interval_days, k, day_rule, nth, weekday, holidays)
    if is_working_day(d, holidays):
        return d
    if policy == "previous":
        earlier = previous_working_day(d, holidays)
        return earlier if earlier >= start else next_working_day(d, holidays)  # never before the rule's own start
    if policy in ("keep", "skip") or frequency == "workdays":
        return d
    return next_working_day(d, holidays)


def period(frequency, nominal_date, start=None):
    """The period a nominal date belongs to. Daily, every working day and the day-count rules are their own date; a weekly rule covers
    its week (counted from Monday), monthly the calendar month, quarterly the quarter, semi-annual the half year, yearly the year."""
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
    return nominal_date  # daily, workdays, every 2 weeks, every N days: each occurrence is its own period
