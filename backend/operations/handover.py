"""Handover from Commercial to Operation, and the Project it creates.

Commercial fills it in (services, scope, contacts, start date, special requirements: never prices, payment terms or the contract) and
submits it. The Operation head accepts it (a Project is created, once), returns it with a comment, or escalates it to the CEO with a
reason; the CEO then accepts or returns it. Every step is checked against the current state under a row lock, so two clicks or two
people never create two projects or move a handover twice.
"""
from datetime import date

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import User
from audit.models import record
from core.models import Sequence
from notifications.service import notify, notify_many

from .models import Handover, Project

H = Handover.Status
MSG_STATE = "That can't be done in the current state."
MSG_NOT_YOURS = "Only the Commercial person on this deal can fill in the handover."
MSG_EMPTY = "Describe the services and the scope before you submit."
MSG_COMMENT = "Write what needs to change."
MSG_REASON = "Write why you are escalating this to the CEO."
MSG_DECIDE = "Only the Operation head or the CEO can do this."
MSG_ESCALATE = "Only the Operation head can escalate."
TEXT_FIELDS = ("services", "scope_notes", "contacts", "special_requirements")
LIMIT = 4000


def link(h):
    return f"/handovers/{h.pk}"


def _locked(h):
    return Handover.objects.select_for_update().select_related("contract", "client", "prepared_by", "contract__lead").get(pk=h.pk)


def _require(h, *states):
    if h.status not in states:
        raise ValidationError({"detail": MSG_STATE})


def operation_heads():
    return User.objects.filter(is_active=True, department__name="Operation", is_dept_head=True)


def ceo_users():
    return User.objects.filter(is_active=True, role_ref__key="ceo")


def can_write(user, h):
    """The Commercial person who owns the deal, or any Commercial head."""
    return user.has_capability("handover.write") and (h.prepared_by_id == user.pk or user.has_capability("lead.manage"))


def create_for_contract(actor, contract):
    """Called when HR marks a signed contract as handed over. One handover per contract; calling twice returns the same one."""
    existing = Handover.objects.filter(contract=contract).first()
    if existing:
        return existing
    lead = contract.lead
    owner = lead.assigned_to or contract.requested_by
    with transaction.atomic():
        h = Handover.objects.create(ref=Sequence.next_ref("HO"), contract=contract, client=contract.client, prepared_by=owner)
        record(actor, h, "created", to_value=h.ref)
    notify(owner, "handover_requested", link=link(h), ref=h.ref, name=lead.company_name)
    return h


def save(actor, h, data):
    """Commercial edits the working copy (draft or returned). Only the whitelisted fields are read; anything else is ignored."""
    with transaction.atomic():
        h = _locked(h)
        _require(h, H.DRAFT, H.RETURNED)
        if not can_write(actor, h):
            raise PermissionDenied(MSG_NOT_YOURS)
        errors = {}
        for f in TEXT_FIELDS:
            if f in data:
                v = str(data[f] or "").strip()
                if len(v) > LIMIT:
                    errors[f] = [f"Keep this under {LIMIT} characters."]
                else:
                    setattr(h, f, v)
        if "start_date" in data:
            raw = data["start_date"]
            if raw in (None, ""):
                h.start_date = None
            else:
                try:
                    h.start_date = date.fromisoformat(str(raw))
                except ValueError:
                    errors["start_date"] = ["Choose a valid date."]
        if errors:
            raise ValidationError(errors)
        h.save()
        record(actor, h, "handover_saved")
    return h


def submit(actor, h):
    with transaction.atomic():
        h = _locked(h)
        _require(h, H.DRAFT, H.RETURNED)
        if not can_write(actor, h):
            raise PermissionDenied(MSG_NOT_YOURS)
        if not h.services.strip():
            raise ValidationError({"services": [MSG_EMPTY]})
        if not h.scope_notes.strip():
            raise ValidationError({"scope_notes": [MSG_EMPTY]})
        prev = h.status
        h.status, h.submitted_at, h.decision_comment = H.SUBMITTED, timezone.now(), ""
        h.save()
        record(actor, h, "handover_submitted", from_value=prev, to_value=H.SUBMITTED)
    notify_many(operation_heads(), "handover_submitted", exclude=actor, link=link(h), ref=h.ref, name=h.client.company_name)
    return h


def _may_decide(user):
    if not user.has_capability("handover.decide"):
        raise PermissionDenied(MSG_DECIDE)


def accept(actor, h):
    """Creates the Project. Safe against a double click and against two deciders at once (row lock, one-to-one constraint)."""
    _may_decide(actor)
    with transaction.atomic():
        h = _locked(h)
        _require(h, H.SUBMITTED, H.ESCALATED)
        prev = h.status
        h.status, h.decided_by, h.decided_at, h.decision_comment = H.ACCEPTED, actor, timezone.now(), ""
        h.save()
        project = Project.objects.create(
            ref=Sequence.next_ref("PRJ"), client=h.client, handover=h, name=h.client.company_name, start_date=h.start_date, created_by=actor,
        )
        record(actor, h, "handover_accepted", from_value=prev, to_value=project.ref)
        record(actor, project, "created", to_value=project.ref)
    notify(h.prepared_by, "handover_accepted", link=link(h), ref=h.ref, name=h.client.company_name)
    return h


def send_back(actor, h, comment):
    _may_decide(actor)
    comment = (comment or "").strip()
    if not comment:
        raise ValidationError({"comment": [MSG_COMMENT]})
    with transaction.atomic():
        h = _locked(h)
        _require(h, H.SUBMITTED, H.ESCALATED)
        prev = h.status
        h.status, h.decided_by, h.decided_at, h.decision_comment = H.RETURNED, actor, timezone.now(), comment[:2000]
        h.save()
        record(actor, h, "handover_returned", from_value=prev, to_value=H.RETURNED, comment=comment[:300])
    notify(h.prepared_by, "handover_returned", link=link(h), ref=h.ref, name=h.client.company_name)
    return h


def escalate(actor, h, reason):
    if not actor.has_capability("operation.manage"):
        raise PermissionDenied(MSG_ESCALATE)
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": [MSG_REASON]})
    with transaction.atomic():
        h = _locked(h)
        _require(h, H.SUBMITTED)
        h.status, h.escalated_by, h.escalated_at, h.escalation_reason = H.ESCALATED, actor, timezone.now(), reason[:2000]
        h.save()
        record(actor, h, "handover_escalated", from_value=H.SUBMITTED, to_value=H.ESCALATED, comment=reason[:300])
    notify_many(ceo_users(), "handover_escalated", exclude=actor, link=link(h), ref=h.ref, name=h.client.company_name)
    notify(h.prepared_by, "handover_escalated", link=link(h), ref=h.ref, name=h.client.company_name)
    return h
