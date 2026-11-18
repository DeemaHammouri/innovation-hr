"""Meeting reports: one per completed appointment. draft -> signed (Commercial head, drawn signature + stamp) -> approved (CEO),
or the CEO returns it with a comment and the author edits it and the head signs again."""
from datetime import date

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import User
from audit.models import record
from core.models import CompanyProfile
from notifications.service import notify_many

from .models import MeetingReport

R = MeetingReport.Status
MSG_STATE = "This report can't do that in its current state."
MSG_NOT_DONE = "Complete the meeting before writing its report."
MSG_NO_LEAD = "A report belongs to a meeting with a client or lead."
MSG_EXISTS = "This meeting already has a report."
MSG_COMMENT = "Write what needs to change."
MSG_STAMP = "The CEO must upload the company stamp (Company details) before a report can be signed."
MSG_EMPTY = "Write what was discussed."
MSG_NOT_YOURS = "You can only change your own reports."
TEXT = (("attendees", 2000), ("summary", 10000), ("decisions", 5000), ("next_steps", 5000))


def link(r):
    return f"/meetings/{r.pk}"


def ref(r):
    return f"MR-{r.pk:05d}"


def _locked(r):
    return MeetingReport.objects.select_for_update(of=("self",)).select_related("lead", "appointment", "author", "signed_by").get(pk=r.pk)


def _require(r, *states):
    if r.status not in states:
        raise ValidationError({"detail": MSG_STATE})


def commercial_head():
    return User.objects.filter(is_active=True, department__name="Commercial", is_dept_head=True).first()


def ceo_users():
    return list(User.objects.filter(is_active=True, role_ref__key="ceo"))


def _fields(data):
    return {k: str(data.get(k) or "").strip()[:limit] for k, limit in TEXT if k in data}


def create(actor, appointment, data):
    from appointments import services as appts

    if appointment.status != "done":
        raise ValidationError({"detail": MSG_NOT_DONE})
    if appointment.lead_id is None:
        raise ValidationError({"detail": MSG_NO_LEAD})
    if not (appts.can_manage(actor, appointment) or actor.has_capability("meeting_report.view_all")):
        raise PermissionDenied(MSG_NOT_YOURS)
    fields = _fields(data)
    if not fields.get("summary"):
        raise ValidationError({"summary": [MSG_EMPTY]})
    held = timezone.localtime(appointment.closed_at or appointment.starts_at).date()
    try:
        with transaction.atomic():
            r = MeetingReport.objects.create(appointment=appointment, lead=appointment.lead, author=actor, held_on=held, **fields)
            record(actor, r, "created")
    except IntegrityError:
        raise ValidationError({"detail": MSG_EXISTS})
    head = commercial_head()
    notify_many([head] if head else [], "report_sign", exclude=actor, link=link(r), ref=ref(r), name=appointment.lead.company_name)
    return r


def update(actor, r, data):
    with transaction.atomic():
        r = _locked(r)
        _require(r, R.DRAFT, R.RETURNED)
        if r.author_id != actor.pk and not actor.has_capability("meeting_report.sign"):
            raise PermissionDenied(MSG_NOT_YOURS)
        for k, v in _fields(data).items():
            setattr(r, k, v)
        if "held_on" in data:
            try:
                r.held_on = date.fromisoformat(str(data["held_on"]))
            except ValueError:
                raise ValidationError({"held_on": ["Use a date like 2026-01-31."]})
        if not r.summary.strip():
            raise ValidationError({"summary": [MSG_EMPTY]})
        r.save()
        record(actor, r, "updated")
    return r


def sign(actor, r, signature):
    from quotations.services import read_signature

    png = read_signature(signature)
    stamp = CompanyProfile.get().stamp
    if not stamp:
        raise ValidationError({"stamp": [MSG_STAMP]})
    with transaction.atomic():
        r = _locked(r)
        _require(r, R.DRAFT, R.RETURNED)
        r.status, r.signed_by, r.signed_at, r.ceo_comment = R.SIGNED, actor, timezone.now(), ""
        r.signature.save("signature.png", ContentFile(png), save=False)
        with stamp.open("rb") as fh:
            r.stamp.save("stamp.png", ContentFile(fh.read()), save=False)
        r.save()
        record(actor, r, "signed")
    notify_many(ceo_users(), "report_approve", link=link(r), ref=ref(r), name=r.lead.company_name)
    return r


def approve(actor, r):
    with transaction.atomic():
        r = _locked(r)
        _require(r, R.SIGNED)
        r.status, r.ceo_by, r.ceo_at = R.APPROVED, actor, timezone.now()
        r.save()
        record(actor, r, "approved")
    notify_many([r.author, r.signed_by], "report_approved", exclude=actor, link=link(r), ref=ref(r), name=r.lead.company_name)
    return r


def return_(actor, r, comment):
    comment = (comment or "").strip()
    if not comment:
        raise ValidationError({"comment": [MSG_COMMENT]})
    with transaction.atomic():
        r = _locked(r)
        _require(r, R.SIGNED)
        r.status, r.ceo_comment = R.RETURNED, comment[:2000]
        r.save()
        record(actor, r, "returned", comment=comment[:300])
    notify_many([r.author, r.signed_by], "returned", exclude=actor, link=link(r), ref=ref(r), name=r.lead.company_name)
    return r
