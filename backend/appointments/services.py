"""Everything that changes an appointment goes through here, so its side effects (the lead's follow-up date, notifications, the
history line) happen in the same transaction."""
from datetime import datetime, time

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import User
from audit.models import record
from notifications.service import notify

from .models import Appointment

A = Appointment
FOLLOW_UP_HOUR = time(9, 0)  # a follow-up made from a lead's outcome (which only has a date) is placed at 09:00, company time

MSG_TITLE = "Add a title."
MSG_TYPE = "Choose the kind of appointment."
MSG_START = "Choose a date and time."
MSG_PAST = "Choose a time that hasn't passed yet."
MSG_END = "The end must be after the start."
MSG_OWNER = "Choose someone who can have appointments."
MSG_CLOSED = "This appointment is already closed."
MSG_NOT_YOURS = "You can only change your own appointments."
MSG_ASSIGN = "Only the Commercial head can give an appointment to someone else."
MSG_LEAD = "You can't see that lead."
MSG_LEAD_FOLLOW_UP = "This is the follow-up of a waiting lead. Reschedule it, or record the lead's outcome instead."
MSG_FOLLOW_UP_LEAD = "A follow-up belongs to a lead. Choose the lead."
MSG_TYPE_LOCK = "A follow-up can't be turned into another kind, or the other way round."


def link(a):
    return f"/appointments?open={a.pk}"


def local_when(a):
    return timezone.localtime(a.starts_at).strftime("%Y-%m-%d %H:%M")


def can_manage(user, appt):
    return appt.owner_id == user.pk or appt.created_by_id == user.pk or user.has_capability("appointment.assign")


def eligible_owner(user):
    return bool(user and user.is_active and user.has_capability("appointment.access"))


def _clean(data, *, partial=False):
    out = {}
    if "title" in data or not partial:
        out["title"] = str(data.get("title") or "").strip()
        if not out["title"]:
            raise ValidationError({"title": [MSG_TITLE]})
        if len(out["title"]) > 200:
            raise ValidationError({"title": ["Keep the title under 200 characters."]})
    if "type" in data or not partial:
        out["type"] = data.get("type") or A.Type.MEETING
        if out["type"] not in A.Type.values:
            raise ValidationError({"type": [MSG_TYPE]})
    if "notes" in data:
        out["notes"] = str(data.get("notes") or "").strip()[:2000]
    return out


def _when(value, field="starts_at"):
    if isinstance(value, str):
        from django.utils.dateparse import parse_datetime

        value = parse_datetime(value)
    if not isinstance(value, datetime):
        raise ValidationError({field: [MSG_START]})
    return timezone.make_aware(value) if timezone.is_naive(value) else value


def create(actor, data):
    from leads import access as lead_access
    from leads.models import Lead

    fields = _clean(data)
    starts_at = _when(data.get("starts_at"))
    if starts_at <= timezone.now():
        raise ValidationError({"starts_at": [MSG_PAST]})
    ends_at = _when(data["ends_at"], "ends_at") if data.get("ends_at") else None
    if ends_at and ends_at <= starts_at:
        raise ValidationError({"ends_at": [MSG_END]})
    lead = None
    if data.get("lead"):
        lead = Lead.objects.filter(pk=data["lead"]).first() if str(data["lead"]).isdigit() else None
        if lead is None or not lead_access.can_view(actor, lead):
            raise ValidationError({"lead": [MSG_LEAD]})
    if fields["type"] == A.Type.FOLLOW_UP and lead is None:
        raise ValidationError({"lead": [MSG_FOLLOW_UP_LEAD]})
    owner = actor
    if data.get("owner") and str(data["owner"]) != str(actor.pk):
        if not actor.has_capability("appointment.assign"):
            raise PermissionDenied(MSG_ASSIGN)
        owner = User.objects.filter(pk=data["owner"]).first() if str(data["owner"]).isdigit() else None
        if not eligible_owner(owner):
            raise ValidationError({"owner": [MSG_OWNER]})
    with transaction.atomic():
        appt = Appointment.objects.create(**fields, lead=lead, owner=owner, created_by=actor, starts_at=starts_at, ends_at=ends_at)
        if lead:
            record(actor, lead, "appointment_created", to_value=local_when(appt), comment=appt.title[:200])
    if owner.pk != actor.pk:
        notify(owner, "appointment_assigned", link=link(appt), actor=actor.full_name, name=appt.title, when=local_when(appt))
    return appt


def update(actor, appt, data):
    _require_open(actor, appt)
    fields = _clean(data, partial=True)
    if "type" in fields and fields["type"] != appt.type and (appt.type == A.Type.FOLLOW_UP or fields["type"] == A.Type.FOLLOW_UP):
        raise ValidationError({"type": [MSG_TYPE_LOCK]})
    for k, v in fields.items():
        setattr(appt, k, v)
    appt.save()
    return appt


def _require_open(actor, appt):
    if appt.status != A.Status.SCHEDULED:
        raise ValidationError({"detail": MSG_CLOSED})
    if not can_manage(actor, appt):
        raise PermissionDenied(MSG_NOT_YOURS)


def _others(actor, appt):
    """The people to tell about a change someone else made: the owner, and whoever made it."""
    return [u for u in {appt.owner_id: appt.owner, appt.created_by_id: appt.created_by}.values() if u.pk != actor.pk]


def reschedule(actor, appt, starts_at, ends_at=None):
    with transaction.atomic():
        appt = Appointment.objects.select_for_update().select_related("lead", "owner", "created_by").get(pk=appt.pk)
        _require_open(actor, appt)
        starts_at = _when(starts_at)
        if starts_at <= timezone.now():
            raise ValidationError({"starts_at": [MSG_PAST]})
        end = _when(ends_at, "ends_at") if ends_at else None
        if end and end <= starts_at:
            raise ValidationError({"ends_at": [MSG_END]})
        old = local_when(appt)
        appt.starts_at, appt.ends_at = starts_at, end
        appt.save()
        lead = appt.lead
        if appt.type == A.Type.FOLLOW_UP and lead and lead.status == "waiting":
            lead.next_follow_up = timezone.localtime(starts_at).date()  # the lead's follow-up date always mirrors its follow-up appointment
            lead.save()
        if lead:
            record(actor, lead, "appointment_rescheduled", from_value=old, to_value=local_when(appt), comment=appt.title[:200])
    for person in _others(actor, appt):
        notify(person, "appointment_rescheduled", link=link(appt), actor=actor.full_name, name=appt.title, when=local_when(appt))
    return appt


def cancel(actor, appt, reason=""):
    with transaction.atomic():
        appt = Appointment.objects.select_for_update().select_related("lead", "owner", "created_by").get(pk=appt.pk)
        _require_open(actor, appt)
        if appt.type == A.Type.FOLLOW_UP and appt.lead_id and appt.lead.status == "waiting":
            raise ValidationError({"detail": MSG_LEAD_FOLLOW_UP})
        _close(appt, A.Status.CANCELLED, reason)
        if appt.lead_id:
            record(actor, appt.lead, "appointment_cancelled", from_value=local_when(appt), comment=appt.title[:200])
    for person in _others(actor, appt):
        notify(person, "appointment_cancelled", link=link(appt), actor=actor.full_name, name=appt.title, when=local_when(appt))
    return appt


def complete(actor, appt):
    with transaction.atomic():
        appt = Appointment.objects.select_for_update().get(pk=appt.pk)
        _require_open(actor, appt)
        _close(appt, A.Status.DONE)
    return appt


def _close(appt, status, reason=""):
    appt.status = status
    appt.closed_at = timezone.now()
    appt.cancel_reason = (reason or "")[:200]
    appt.save()


# ---- called by the lead workflow, inside its own transaction ----
def sync_follow_up(lead, actor, day):
    """A lead went (or stayed) Waiting with a follow-up date: exactly one open follow-up appointment, on that date, for whoever has the lead."""
    owner = lead.assigned_to if lead.assigned_to_id and lead.assigned_to.is_active else actor
    when = timezone.make_aware(datetime.combine(day, FOLLOW_UP_HOUR))
    for appt in list(lead.appointments.filter(type=A.Type.FOLLOW_UP, status=A.Status.SCHEDULED)):
        _close(appt, A.Status.CANCELLED, "Replaced by a new follow-up")
    appt = Appointment.objects.create(type=A.Type.FOLLOW_UP, title=lead.company_name[:200], lead=lead, owner=owner, created_by=actor, starts_at=when)
    record(actor, lead, "appointment_created", to_value=local_when(appt), comment="Follow-up")
    return appt


def cancel_open_follow_ups(lead, actor, why):
    """The lead was rejected or accepted: nothing is left to follow up."""
    cancelled = 0
    for appt in lead.appointments.filter(type=A.Type.FOLLOW_UP, status=A.Status.SCHEDULED).select_related("owner"):
        _close(appt, A.Status.CANCELLED, why)
        cancelled += 1
        if appt.owner_id != actor.pk:
            notify(appt.owner, "appointment_cancelled", link=link(appt), actor=actor.full_name, name=appt.title, when=local_when(appt))
    if cancelled:
        record(actor, lead, "followups_cancelled", to_value=str(cancelled), comment=why[:200])
    return cancelled
