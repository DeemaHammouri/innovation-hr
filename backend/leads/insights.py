"""Leads dashboard and the monthly target. Every day boundary is a midnight in the company time zone (settings.TIME_ZONE), never UTC.

Definitions (also shown to the user):
- "added" = leads created in the period, archived ones left out.
- contact rate    = leads that were ever contacted / leads added.
- acceptance rate = leads accepted (qualified) / leads that were ever contacted.
- follow-up due = a waiting lead whose follow-up date is today; overdue = before today.
- target (one Marketing employee, date A to date B, both included): elapsed days count today; expected by today = target x elapsed / days
  in the range; on track when added >= expected;
  required per day = remaining / days left (when no day is left, what is still missing has to happen today).
"""
from datetime import datetime, time, timedelta

from django.db.models import Count
from django.utils import timezone

from .access import visible_q
from .models import Lead


def day_start(d):
    return timezone.make_aware(datetime.combine(d, time.min))


def added_between(qs, first, last):
    """Leads created on company-time days first..last inclusive."""
    return qs.filter(created_at__gte=day_start(first), created_at__lt=day_start(last + timedelta(days=1)))


def per_day(qs, first, last):
    """{date: count} for every day in first..last (zeros included), counted in the company time zone."""
    counts = {first + timedelta(days=i): 0 for i in range((last - first).days + 1)}
    for created in added_between(qs, first, last).values_list("created_at", flat=True):
        counts[timezone.localtime(created).date()] += 1
    return counts


def dashboard(user, today=None):
    today = today or timezone.localdate()
    qs = Lead.objects.filter(visible_q(user), archived_at__isnull=True)
    month_first = today.replace(day=1)
    total = qs.count()
    contacted = qs.filter(first_contacted_at__isnull=False).count()
    accepted = qs.filter(status=Lead.Status.QUALIFIED).count()
    waiting = qs.filter(status=Lead.Status.WAITING)
    days = per_day(qs, today - timedelta(days=29), today)
    by_status = {s: 0 for s in Lead.Status.values}
    by_status.update({r["status"]: r["n"] for r in qs.values("status").annotate(n=Count("id"))})
    return {
        "today": today.isoformat(),
        "total": total,
        "added": {
            "today": added_between(qs, today, today).count(),
            "last_7_days": added_between(qs, today - timedelta(days=6), today).count(),
            "this_month": added_between(qs, month_first, today).count(),
        },
        "contact_rate": round(contacted / total * 100, 1) if total else 0,
        "acceptance_rate": round(accepted / contacted * 100, 1) if contacted else 0,
        "follow_ups": {
            "due_today": waiting.filter(next_follow_up=today).count(),
            "overdue": waiting.filter(next_follow_up__lt=today).count(),
        },
        "per_day": [{"date": d.isoformat(), "count": n} for d, n in days.items()],
        "by_status": [{"status": s, "count": n} for s, n in by_status.items()],
        "by_source": [{"source": r["source"], "count": r["n"]} for r in qs.values("source").annotate(n=Count("id")).order_by("-n", "source")[:10]],
        "top_contributors": [
            {"id": r["created_by"], "name": r["created_by__full_name"], "count": r["n"]}
            for r in qs.values("created_by", "created_by__full_name").annotate(n=Count("id")).order_by("-n", "created_by__full_name")[:5]
        ],
    }


def progress(target, today=None):
    """Progress of one LeadTarget on `today` (company time zone). Both end dates are included.

    Outside the range: before it nothing has elapsed; after it everything has. "Required per day" only means something while
    the range is running."""
    today = today or timezone.localdate()
    first, last = target.start_date, target.end_date
    n_days = (last - first).days + 1
    elapsed = 0 if today < first else n_days if today > last else (today - first).days + 1
    left = n_days - elapsed
    qs = Lead.objects.filter(archived_at__isnull=True)
    if target.user_id:
        qs = qs.filter(created_by_id=target.user_id)
    days = per_day(qs, first, last)
    added = sum(n for d, n in days.items() if d <= today)
    goal = target.target
    remaining = max(goal - added, 0)
    expected = goal * elapsed / n_days
    chart, run = [], 0
    for i, (d, n) in enumerate(days.items(), start=1):
        past = d <= today
        run += n if past else 0
        chart.append({"date": d.isoformat(), "count": n if past else None, "total": run if past else None, "plan": round(goal * i / n_days, 1)})
    live = first <= today <= last
    return {
        "id": target.pk, "user": target.user_id, "user_name": target.user.full_name if target.user_id else None,
        "start_date": first.isoformat(), "end_date": last.isoformat(), "target": goal,
        "set_by": target.set_by_id, "set_by_name": target.set_by.full_name,
        "state": "upcoming" if today < first else "ended" if today > last else "active",
        "added": added, "remaining": remaining,
        "percent": round(added / goal * 100, 1),
        "days_in_range": n_days, "days_elapsed": elapsed, "days_left": left,
        "expected_by_today": round(expected, 1),
        "on_track": (added >= expected) if elapsed else None,
        "required_per_day": (round(remaining / left, 1) if left else float(remaining)) if live else None,
        "days": chart,
    }
