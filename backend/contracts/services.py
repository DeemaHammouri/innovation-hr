"""
The contract workflow. Every transition checks its own state, so an invalid move is refused here whatever the screen showed.

requested -> drafting -> with_commercial -> meeting_logged -> ceo_review -> signed -> handed_over
                ^              ^                                  |
                +--- returned -+------ (CEO returns with a comment)
Cancelled (reason, Commercial head) is possible from any open state.
"""
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from audit.models import record
from core.access import content_type_for
from core.models import Sequence
from files.models import Attachment
from notifications.service import notify_many

from .models import OPEN, Contract, ContractVersion

MSG_NOT_READY = "A contract can start once the quotation is confirmed or skipped."
MSG_OPEN_EXISTS = "This lead already has a contract in progress."
MSG_STATE = "This contract can't do that in its current state."
MSG_NO_DRAFT = "Upload the draft contract file before sending it to Commercial."
MSG_MEETING_DATE = "Choose the date the meeting took place."
MSG_MEETING_FUTURE = "The meeting date can't be in the future."
MSG_MEETING_NOTES = "Write what was discussed in the meeting."
MSG_NO_VISIT = "Upload the visit report before sending this to the CEO."
MSG_NO_SIGNED_COPY = "Upload the copy signed by the client before sending this to the CEO."
MSG_COMMENT = "Write what needs to change."
MSG_CANCEL = "Write why you are cancelling this contract."
MSG_NO_FINAL = "Upload the final signed contract before handing it over."

S = Contract.Status


def link(c):
    return f"/contracts/{c.pk}"


def _locked(c):
    return Contract.objects.select_for_update().select_related("lead", "lead__assigned_to").get(pk=c.pk)


def _require(c, *states):
    if c.status not in states:
        raise ValidationError({"detail": MSG_STATE})


def hr_users():
    return User.objects.filter(is_active=True, department__name="HR")


def ceo_users():
    from core.roles import CEO, role_key

    return [u for u in User.objects.filter(is_active=True, department__name="Administration") if role_key(u) == CEO]


def pipeline_users(c):
    who = [c.lead.assigned_to] if c.lead.assigned_to_id and c.lead.assigned_to.is_active else []
    head = User.objects.filter(is_active=True, department__name="Commercial", role=User.Role.HEAD).first()
    return who + ([head] if head and head not in who else [])


def files(c, *categories):
    return Attachment.objects.filter(content_type=content_type_for(Contract), object_id=c.pk, archived_at__isnull=True, category__in=categories)


def request_contract(actor, lead, note=""):
    note = (note or "").strip()[:1000]
    if lead.archived_at or lead.status != "qualified":
        raise ValidationError({"detail": MSG_NOT_READY})
    confirmed = lead.quotations.filter(status="confirmed").order_by("-outcome_at", "-id").first()
    if not (lead.skipped_quotation_at or confirmed):
        raise ValidationError({"detail": MSG_NOT_READY})
    try:
        with transaction.atomic():
            if lead.contracts.filter(status__in=OPEN).exists():
                raise ValidationError({"detail": MSG_OPEN_EXISTS})
            c = Contract.objects.create(ref=Sequence.next_ref("CT"), lead=lead, quotation=confirmed, requested_by=actor, request_note=note)
            record(actor, c, "requested", comment=note[:300])
            record(actor, lead, "contract_requested", to_value=c.ref)
    except IntegrityError:
        raise ValidationError({"detail": MSG_OPEN_EXISTS})
    notify_many(hr_users(), "request_received", exclude=actor, link=link(c), ref=c.ref, name=lead.company_name)
    return c


def start_drafting(actor, c):
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.REQUESTED, S.RETURNED)
        was = c.status
        c.status, c.drafted_by = S.DRAFTING, actor
        c.save(update_fields=["status", "drafted_by", "updated_at"])
        record(actor, c, "drafting_started" if was == S.REQUESTED else "redrafting_started", from_value=was, to_value=c.status)
    return c


def send_to_commercial(actor, c, note=""):
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.DRAFTING)
        last = c.versions.order_by("-number").first()
        fresh = files(c, "draft")
        if last:
            fresh = fresh.filter(created_at__gt=last.created_at)
        if not fresh.exists():
            raise ValidationError({"detail": MSG_NO_DRAFT})
        v = ContractVersion.objects.create(contract=c, number=(last.number if last else 0) + 1, note=(note or "").strip()[:1000], created_by=actor)
        c.status = S.WITH_COMMERCIAL
        c.save(update_fields=["status", "updated_at"])
        record(actor, c, "sent_to_commercial", to_value=f"v{v.number}", comment=v.note[:300])
    notify_many(pipeline_users(c), "request_received", exclude=actor, link=link(c), ref=c.ref, name=c.lead.company_name)
    return c


def log_meeting(actor, c, meeting_date, notes):
    notes = (notes or "").strip()
    if not isinstance(meeting_date, date):
        raise ValidationError({"meeting_date": [MSG_MEETING_DATE]})
    if meeting_date > timezone.localdate():
        raise ValidationError({"meeting_date": [MSG_MEETING_FUTURE]})
    if not notes:
        raise ValidationError({"meeting_notes": [MSG_MEETING_NOTES]})
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.WITH_COMMERCIAL, S.RETURNED)
        c.status, c.meeting_date, c.meeting_notes, c.meeting_by = S.MEETING_LOGGED, meeting_date, notes[:3000], actor
        c.save(update_fields=["status", "meeting_date", "meeting_notes", "meeting_by", "updated_at"])
        record(actor, c, "meeting_logged", to_value=meeting_date.isoformat(), comment=notes[:300])
    return c


def submit_to_ceo(actor, c):
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.MEETING_LOGGED)
        if not files(c, "visit_report").exists():
            raise ValidationError({"detail": MSG_NO_VISIT})
        if not files(c, "client_signed_copy").exists():
            raise ValidationError({"detail": MSG_NO_SIGNED_COPY})
        c.status, c.submitted_to_ceo_at, c.ceo_comment = S.CEO_REVIEW, timezone.now(), ""
        c.save(update_fields=["status", "submitted_to_ceo_at", "ceo_comment", "updated_at"])
        record(actor, c, "submitted_to_ceo")
    notify_many(ceo_users(), "contract_review", link=link(c), ref=c.ref, name=c.lead.company_name)
    return c


def ceo_return(actor, c, comment):
    comment = (comment or "").strip()
    if not comment:
        raise ValidationError({"comment": [MSG_COMMENT]})
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.CEO_REVIEW)
        c.status, c.ceo_comment = S.RETURNED, comment[:2000]
        c.save(update_fields=["status", "ceo_comment", "updated_at"])
        record(actor, c, "returned_by_ceo", comment=comment[:300])
    notify_many(list(hr_users()) + pipeline_users(c), "returned", exclude=actor, link=link(c), ref=c.ref, name=c.lead.company_name)
    return c


def ceo_sign(actor, c):
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.CEO_REVIEW)
        c.status, c.signed_by, c.signed_at = S.SIGNED, actor, timezone.now()
        c.save(update_fields=["status", "signed_by", "signed_at", "updated_at"])
        record(actor, c, "signed")
    notify_many(list(hr_users()) + pipeline_users(c), "signed", exclude=actor, link=link(c), ref=c.ref, name=c.lead.company_name)
    return c


def hand_over(actor, c):
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.SIGNED)
        if not files(c, "final_signed").exists():
            raise ValidationError({"detail": MSG_NO_FINAL})
        c.status, c.handed_over_by, c.handed_over_at = S.HANDED_OVER, actor, timezone.now()
        c.save(update_fields=["status", "handed_over_by", "handed_over_at", "updated_at"])
        record(actor, c, "handed_over")
        record(actor, c.lead, "contract_handed_over", to_value=c.ref)
    ops = User.objects.filter(is_active=True, department__name="Operation")
    notify_many(ops, "contract_handover", exclude=actor, link=link(c), ref=c.ref, name=c.lead.company_name)
    return c


def cancel(actor, c, reason):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": [MSG_CANCEL]})
    with transaction.atomic():
        c = _locked(c)
        _require(c, *OPEN)
        c.status, c.cancel_reason = S.CANCELLED, reason[:1000]
        c.save(update_fields=["status", "cancel_reason", "updated_at"])
        record(actor, c, "cancelled", comment=reason[:300])
    return c
