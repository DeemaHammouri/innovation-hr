"""Leave: requests, balances and the decision. Days are working days (weekends excluded; there is no public-holiday calendar)."""
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from audit.models import record
from notifications.service import notify

from .models import LeaveRequest, LeaveType

MSG_STATE = "That can't be done in the current state."
MSG_TYPE = "Choose a leave type."
MSG_DATES = "Choose valid start and end dates."
MSG_ORDER = "The end date can't be before the start date."
MSG_PAST = "Leave can't start more than 30 days in the past."
MSG_LONG = "A request can cover up to 366 days."
MSG_YEAR = "A request must stay within one calendar year. Split it in two."
MSG_NO_DAYS = "Those dates have no working days."
MSG_REASON_LONG = "Keep the reason under 500 characters."
MSG_OVERLAP = "You already have leave requested or approved on some of these dates."
MSG_BALANCE = "That is more than the days left for this leave type."
MSG_NOTE = "Write why you are rejecting this request."
MSG_NOTE_LONG = "Keep this under 500 characters."
MSG_NOT_YOURS = "You can only cancel your own request."
MSG_STARTED = "Leave that has already started can't be cancelled. Ask HR."
MSG_NAME = "Enter the leave type name in both languages."
MSG_ALLOWANCE = "Enter a number of days from 1 to 366, or leave it empty for no limit."


def weekend():
    return set(getattr(settings, "WEEKEND_DAYS", (4, 5)))  # Friday and Saturday


def working_days(start, end):
    off, n, d = weekend(), 0, start
    while d <= end:
        n += d.weekday() not in off
        d += timedelta(days=1)
    return n


def _date(raw):
    try:
        return date.fromisoformat(str(raw)[:10])
    except (ValueError, TypeError):
        raise ValidationError({"start_date": MSG_DATES})


def used_days(user, leave_type, year, exclude=None):
    qs = LeaveRequest.objects.filter(user=user, leave_type=leave_type, status="approved", start_date__year=year)
    if exclude:
        qs = qs.exclude(pk=exclude)
    return qs.aggregate(n=Sum("days"))["n"] or 0


def balances(user, year):
    rows = []
    pending = {r["leave_type"]: r["n"] for r in LeaveRequest.objects.filter(user=user, status="pending", start_date__year=year).values("leave_type").annotate(n=Sum("days"))}
    used = {r["leave_type"]: r["n"] for r in LeaveRequest.objects.filter(user=user, status="approved", start_date__year=year).values("leave_type").annotate(n=Sum("days"))}
    for t in LeaveType.objects.filter(is_active=True):
        u = used.get(t.pk, 0)
        rows.append({
            "leave_type": t.pk, "name_en": t.name_en, "name_ar": t.name_ar, "paid": t.paid, "allowance": t.annual_days, "used": u,
            "pending": pending.get(t.pk, 0), "remaining": None if t.annual_days is None else max(t.annual_days - u, 0),
        })
    return rows


def deciders(requester):
    """Who may decide this person's leave: the CEO for the HR head, otherwise the HR head."""
    if requester.department.name == "HR" and requester.is_dept_head:
        return list(User.objects.filter(is_active=True, department__name="Administration", is_dept_head=True))
    return list(User.objects.filter(is_active=True, department__name="HR", is_dept_head=True))


def _overlaps(user, start, end, exclude=None):
    qs = LeaveRequest.objects.filter(user=user, status__in=["pending", "approved"], start_date__lte=end, end_date__gte=start)
    return qs.exclude(pk=exclude).exists() if exclude else qs.exists()


def request_leave(actor, data, today=None):
    today = today or timezone.localdate()
    ltype = LeaveType.objects.filter(pk=int(data["leave_type"]) if str(data.get("leave_type") or "").isdigit() else 0, is_active=True).first()
    if ltype is None:
        raise ValidationError({"leave_type": MSG_TYPE})
    start, end = _date(data.get("start_date")), None
    try:
        end = date.fromisoformat(str(data.get("end_date"))[:10])
    except (ValueError, TypeError):
        raise ValidationError({"end_date": MSG_DATES})
    if end < start:
        raise ValidationError({"end_date": MSG_ORDER})
    if start < today - timedelta(days=30):
        raise ValidationError({"start_date": MSG_PAST})
    if (end - start).days > 365:
        raise ValidationError({"end_date": MSG_LONG})
    if start.year != end.year:
        raise ValidationError({"end_date": MSG_YEAR})
    days = working_days(start, end)
    if days == 0:
        raise ValidationError({"start_date": MSG_NO_DAYS})
    reason = str(data.get("reason") or "").strip()
    if len(reason) > 500:
        raise ValidationError({"reason": MSG_REASON_LONG})
    with transaction.atomic():
        User.objects.select_for_update().get(pk=actor.pk)  # one request at a time per person
        if _overlaps(actor, start, end):
            raise ValidationError({"start_date": MSG_OVERLAP})
        if ltype.annual_days is not None and used_days(actor, ltype, start.year) + days > ltype.annual_days:
            raise ValidationError({"leave_type": MSG_BALANCE})
        req = LeaveRequest.objects.create(user=actor, leave_type=ltype, start_date=start, end_date=end, days=days, reason=reason)
        record(actor, req, "created", to_value=f"{start.isoformat()} - {end.isoformat()}")
    for who in deciders(actor):
        notify(who, "leave_requested", link="/leave?tab=requests", actor=actor.full_name, ref=ltype.name_en if who.preferred_language == "en" else ltype.name_ar, name=f"{start.isoformat()} - {end.isoformat()}")
    return req


def _locked(req_id):
    return LeaveRequest.objects.select_for_update(of=("self",)).select_related("user__department", "leave_type").get(pk=req_id)


def approve(actor, req):
    with transaction.atomic():
        req = _locked(req.pk)
        if req.status != "pending":
            raise ValidationError({"detail": MSG_STATE})
        t = req.leave_type
        if t.annual_days is not None and used_days(req.user, t, req.start_date.year, exclude=req.pk) + req.days > t.annual_days:
            raise ValidationError({"detail": MSG_BALANCE})
        req.status, req.decided_by, req.decided_at = "approved", actor, timezone.now()
        req.save()
        record(actor, req, "approved")
    notify(req.user, "leave_approved", link="/leave", ref=t.name_en if req.user.preferred_language == "en" else t.name_ar, name=f"{req.start_date.isoformat()} - {req.end_date.isoformat()}")
    return req


def reject(actor, req, note):
    note = str(note or "").strip()
    if not note:
        raise ValidationError({"note": MSG_NOTE})
    if len(note) > 500:
        raise ValidationError({"note": MSG_NOTE_LONG})
    with transaction.atomic():
        req = _locked(req.pk)
        if req.status != "pending":
            raise ValidationError({"detail": MSG_STATE})
        req.status, req.decided_by, req.decided_at, req.decision_note = "rejected", actor, timezone.now(), note
        req.save()
        record(actor, req, "rejected", comment=note)
    t = req.leave_type
    notify(req.user, "leave_rejected", link="/leave", ref=t.name_en if req.user.preferred_language == "en" else t.name_ar, name=note[:120])
    return req


def cancel(actor, req, today=None):
    today = today or timezone.localdate()
    with transaction.atomic():
        req = _locked(req.pk)
        if req.user_id != actor.pk:
            raise ValidationError({"detail": MSG_NOT_YOURS})
        if req.status not in ("pending", "approved"):
            raise ValidationError({"detail": MSG_STATE})
        if req.status == "approved" and req.start_date <= today:
            raise ValidationError({"detail": MSG_STARTED})
        was = req.status
        req.status = "cancelled"
        req.save()
        record(actor, req, "cancelled", from_value=was)
    return req


# ---------- leave types ----------
def save_type(actor, data, instance=None):
    en, ar = str(data.get("name_en", instance.name_en if instance else "")).strip(), str(data.get("name_ar", instance.name_ar if instance else "")).strip()
    if not en or not ar or len(en) > 80 or len(ar) > 80:
        raise ValidationError({"name_en": MSG_NAME})
    days = data.get("annual_days", instance.annual_days if instance else None)
    if days in ("", None):
        days = None
    else:
        try:
            days = int(days)
        except (TypeError, ValueError):
            raise ValidationError({"annual_days": MSG_ALLOWANCE})
        if not 1 <= days <= 366:
            raise ValidationError({"annual_days": MSG_ALLOWANCE})
    t = instance or LeaveType()
    t.name_en, t.name_ar, t.annual_days = en, ar, days
    t.paid = bool(data.get("paid", t.paid if instance else True))
    if "is_active" in data:
        t.is_active = bool(data["is_active"])
    t.save()
    return t


# ---------- calendar ----------
def calendar_q(user):
    if user.has_capability("hr.attendance_all"):
        return Q()
    if user.is_dept_head and user.department_id:
        return Q(user__department_id=user.department_id)
    return Q(user=user)
