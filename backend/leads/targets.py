"""Per-employee lead targets: who may set them, what is valid, and the audit line for every change."""
from datetime import date, timedelta

from django.db import transaction
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from accounts.models import User
from audit.models import record
from notifications.service import notify

from .models import LeadTarget

MAX_DAYS = 366
MAX_TARGET = 100000
MSG_USER = "Choose a Marketing employee."
MSG_START = "Choose the first day."
MSG_END = "Choose the last day."
MSG_ORDER = "The last day can't be before the first day."
MSG_LONG = "A target can run for at most one year."
MSG_TARGET = "Enter a whole number between 1 and 100000."
MSG_OVERLAP = "This person already has a target that overlaps these dates."


def is_marketing(user):
    return bool(user and user.is_active and user.role_ref_id and user.role_ref.key == "marketing")


def marketing_people():
    return [u for u in User.objects.filter(is_active=True, role_ref__key="marketing").order_by("full_name")]


def _day(value, field, message):
    if isinstance(value, date):
        return value
    parsed = parse_date(str(value or "")) if value else None
    if parsed is None:
        raise ValidationError({field: [message]})
    return parsed


def _clean(data, current=None):
    start = _day(data.get("start_date", current.start_date if current else None), "start_date", MSG_START)
    end = _day(data.get("end_date", current.end_date if current else None), "end_date", MSG_END)
    if end < start:
        raise ValidationError({"end_date": [MSG_ORDER]})
    if (end - start) >= timedelta(days=MAX_DAYS):
        raise ValidationError({"end_date": [MSG_LONG]})
    value = data.get("target", current.target if current else None)
    if isinstance(value, bool) or not str(value).isdigit() or not (1 <= int(value) <= MAX_TARGET):
        raise ValidationError({"target": [MSG_TARGET]})
    return start, end, int(value)


def _owner(data, current=None):
    if "user" not in data and current is not None:
        return current.user
    raw = data.get("user")
    person = User.objects.filter(pk=raw).first() if str(raw).isdigit() else None
    if not is_marketing(person):
        raise ValidationError({"user": [MSG_USER]})
    return person


def _no_overlap(owner, start, end, exclude_pk=None):
    clash = LeadTarget.objects.filter(user=owner, start_date__lte=end, end_date__gte=start)
    if exclude_pk:
        clash = clash.exclude(pk=exclude_pk)
    if clash.exists():
        raise ValidationError({"start_date": [MSG_OVERLAP]})


def create(actor, data):
    owner = _owner(data)
    start, end, value = _clean(data)
    _no_overlap(owner, start, end)
    with transaction.atomic():
        row = LeadTarget.objects.create(user=owner, start_date=start, end_date=end, target=value, set_by=actor)
        record(actor, row, "target_set", to_value=f"{owner.full_name}: {value} ({start} to {end})")
    notify(owner, "target_assigned", link="/dashboard", actor=actor.full_name, name=f"{value}", when=f"{start} → {end}")
    return row


def update(actor, row, data):
    owner = _owner(data, row)
    start, end, value = _clean(data, row)
    if owner is not None:
        _no_overlap(owner, start, end, exclude_pk=row.pk)
    with transaction.atomic():
        before = f"{row.target} ({row.start_date} to {row.end_date})"
        row.user, row.start_date, row.end_date, row.target = owner, start, end, value
        row.save()
        record(actor, row, "target_changed", from_value=before, to_value=f"{value} ({start} to {end})")
    return row


def remove(actor, row):
    with transaction.atomic():
        record(actor, row, "target_removed", from_value=f"{row.target} ({row.start_date} to {row.end_date})")
        row.delete()
