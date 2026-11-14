"""
Attendance is derived, never stored: for each person and local day, the first sign-in, the last sign-out after it, the hours
between them, and whether the first sign-in was after the CEO's work start plus the grace period.

A day with a sign-in but no later sign-out is shown as "still open" with no hours (a closed browser or an expired session never
signs out, and guessing would be wrong). A sign-out with no sign-in on the same local day is ignored. Days with no sign-in at all
have no row: the system has no weekend or public-holiday calendar to judge absence against.
"""
from collections import defaultdict
from datetime import datetime, time, timedelta

from django.utils import timezone

from accounts.models import ActionLog, User
from lookups.models import WorkHours

MAX_RANGE_DAYS = 93


def bounds(start, end):
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(start, time.min), tz), timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz)


def employees():
    return User.objects.filter(is_active=True, is_superuser=False, department__isnull=False).select_related("department")


def rows_for(users, start, end, late_only=False):
    """One dict per (person, day) that has a sign-in, newest day first. `users` is a queryset or list of User."""
    users = {u.pk: u for u in users}
    if not users:
        return []
    work = WorkHours.get()
    lo, hi = bounds(start, end)
    logs = ActionLog.objects.filter(user_id__in=list(users), timestamp__gte=lo, timestamp__lt=hi).order_by("timestamp").values_list("user_id", "action", "timestamp")
    days = defaultdict(lambda: {"in": None, "out": None})
    for uid, action, ts in logs:
        local = timezone.localtime(ts)
        slot = days[(uid, local.date())]
        if action == ActionLog.Action.LOGIN:
            if slot["in"] is None:
                slot["in"] = local
        elif slot["in"] is not None and local >= slot["in"]:
            slot["out"] = local  # the last sign-out after the first sign-in
    limit = (datetime.combine(start, work.work_start) + timedelta(minutes=work.grace_minutes)).time()
    out = []
    for (uid, day), slot in days.items():
        if slot["in"] is None:
            continue
        first, last = slot["in"], slot["out"]
        late = first.time().replace(second=0, microsecond=0) > limit  # judged to the minute
        if late_only and not late:
            continue
        minutes_late = max(0, int((datetime.combine(day, first.time()) - datetime.combine(day, work.work_start)).total_seconds() // 60))
        out.append({
            "user": uid, "user_name": users[uid].full_name, "department": users[uid].department.name if users[uid].department_id else "",
            "date": day, "first_in": first, "last_out": last,
            "hours": round((last - first).total_seconds() / 3600, 2) if last else None,
            "late": late, "minutes_late": minutes_late if late else 0, "open": last is None,
        })
    out.sort(key=lambda r: (r["date"], r["user_name"].lower()), reverse=True)
    return out


def summary(rows):
    return {
        "days": len(rows), "late_days": sum(1 for r in rows if r["late"]),
        "hours": round(sum(r["hours"] or 0 for r in rows), 2), "open_days": sum(1 for r in rows if r["open"]),
    }
