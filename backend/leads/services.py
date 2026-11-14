"""Everything that changes a lead goes through here: state machine, audit line and notifications in one transaction."""
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from audit.models import record
from core.models import Sequence
from lookups.models import RejectionReason
from notifications.service import notify

from .models import Interaction, Lead, email_key, phone_key
from .validation import clean_lead_fields

L = Lead.Status

MSG_ARCHIVED = "This lead is archived."
MSG_CLOSED = "This lead is already closed."
MSG_FIRST_CONTACT = "Log the first contact before recording an outcome."
MSG_OUTCOME = "Choose what happened: waiting, rejected or accepted."
MSG_FOLLOW_UP = "Choose a follow-up date."
MSG_FOLLOW_UP_PAST = "Choose today or a later date."
MSG_FOLLOW_UP_FAR = "Choose a date within the next year."
MSG_REASON = "Choose why this lead was rejected."
MSG_FUTURE = "Choose a time that has already passed."
MSG_REOPEN_STATE = "Only a rejected lead can be reopened."
MSG_REOPEN_NOTE = "Write a note explaining why you are reopening it."
MSG_ASSIGNEE = "Choose someone from the Commercial team."
MSG_ARCHIVE_REASON = "Write why you are archiving this lead."
MSG_RESTORE = "This lead isn't archived."
MSG_ARCHIVE_DONE = "This lead is already archived."
MSG_TYPE = "Choose how you were in touch."


def commercial_head():
    return User.objects.filter(is_active=True, department__name="Commercial", role=User.Role.HEAD).first()


def link(lead):
    return f"/leads/{lead.pk}"


def find_duplicate(phone, email, exclude_pk=None):
    q = Q()
    if phone_key(phone):
        q |= Q(phone_key=phone_key(phone))
    if email_key(email):
        q |= Q(email_key=email_key(email))
    if not q:
        return None
    qs = Lead.objects.filter(q, archived_at__isnull=True)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.first()


def create_lead(actor, data, *, allow_duplicate=False):
    cleaned, errors = clean_lead_fields(data)
    if errors:
        raise ValidationError({k: [v] for k, v in errors.items()})
    dup = find_duplicate(cleaned["phone"], cleaned["email"])
    if dup and not allow_duplicate:
        raise ValidationError({"duplicate": [dup.ref]})
    with transaction.atomic():
        lead = Lead.objects.create(ref=Sequence.next_ref("LD"), created_by=actor, **cleaned)
        record(actor, lead, "created")
    head = commercial_head()
    if head:
        notify(head, "leads_new", link="/pipeline", count=1, name=lead.company_name)
    return lead


def update_lead(actor, lead, data):
    cleaned, errors = clean_lead_fields({**{k: getattr(lead, k) for k in ("company_name", "contact_name", "phone", "email", "source", "notes")}, **data})
    if errors:
        raise ValidationError({k: [v] for k, v in errors.items()})
    changed = [k for k, v in cleaned.items() if getattr(lead, k) != v]
    if not changed:
        return lead
    with transaction.atomic():
        for k in changed:
            setattr(lead, k, cleaned[k])
        lead.save()
        record(actor, lead, "updated", to_value=", ".join(changed))
    return lead


def assign(actor, lead, assignee):
    if assignee is None or not assignee.is_active or not assignee.department_id or assignee.department.name != "Commercial":
        raise ValidationError({"assigned_to": [MSG_ASSIGNEE]})
    if lead.archived_at:
        raise ValidationError({"detail": MSG_ARCHIVED})
    if lead.assigned_to_id == assignee.pk:
        return lead
    with transaction.atomic():
        old = lead.assigned_to.full_name if lead.assigned_to_id else ""
        lead.assigned_to = assignee
        lead.assigned_at = timezone.now()
        lead.save()
        record(actor, lead, "assigned", from_value=old, to_value=assignee.full_name)
    if assignee.pk != actor.pk:
        notify(assignee, "assigned", link=link(lead), actor=actor.full_name, ref=lead.ref, name=lead.company_name)
    return lead


def _require_open(lead):
    if lead.archived_at:
        raise ValidationError({"detail": MSG_ARCHIVED})
    if lead.status in (L.QUALIFIED, L.REJECTED):
        raise ValidationError({"detail": MSG_CLOSED})


def _apply_outcome(lead, actor, outcome, next_follow_up, reason_id, note):
    """Move the lead to its outcome. The caller saves. Exactly one outcome, each with what it needs."""
    old = lead.status
    now = timezone.now()
    note = (note or "").strip()
    if outcome == "waiting":
        if not next_follow_up:
            raise ValidationError({"next_follow_up": [MSG_FOLLOW_UP]})
        today = timezone.localdate()
        if not isinstance(next_follow_up, date):
            raise ValidationError({"next_follow_up": [MSG_FOLLOW_UP]})
        if next_follow_up < today:
            raise ValidationError({"next_follow_up": [MSG_FOLLOW_UP_PAST]})
        if next_follow_up > today + timedelta(days=366):
            raise ValidationError({"next_follow_up": [MSG_FOLLOW_UP_FAR]})
        lead.status = L.WAITING
        lead.next_follow_up = next_follow_up
        lead.rejection_reason = None
        lead.rejection_note = ""
        record(actor, lead, "outcome_waiting", from_value=old, to_value=next_follow_up.isoformat(), comment=note[:300])
    elif outcome == "rejected":
        reason = RejectionReason.objects.filter(pk=reason_id, is_active=True).first() if reason_id else None
        if reason is None:
            raise ValidationError({"rejection_reason": [MSG_REASON]})
        lead.status = L.REJECTED
        lead.rejection_reason = reason
        lead.rejection_note = note
        lead.rejected_at = now
        lead.next_follow_up = None
        record(actor, lead, "outcome_rejected", from_value=old, comment=note[:300])
        _tell_head(actor, lead, "lead_rejected")
    elif outcome == "accepted":
        lead.status = L.QUALIFIED
        lead.qualified_at = now
        lead.next_follow_up = None
        lead.rejection_reason = None
        lead.rejection_note = ""
        record(actor, lead, "outcome_qualified", from_value=old, comment=note[:300])
        _tell_head(actor, lead, "lead_qualified")
    else:
        raise ValidationError({"outcome": [MSG_OUTCOME]})


def _tell_head(actor, lead, kind):
    head = commercial_head()
    if head and head.pk != actor.pk:
        notify(head, kind, link=link(lead), actor=actor.full_name, ref=lead.ref, name=lead.company_name)


def log_interaction(actor, lead, *, type, occurred_at=None, notes="", outcome="", next_follow_up=None, reason_id=None, note=""):
    """Record a contact. On a new lead this is the first contact. A waiting lead must come out with an outcome again."""
    if type not in Interaction.Type.values:
        raise ValidationError({"type": [MSG_TYPE]})
    now = timezone.now()
    occurred_at = occurred_at or now
    if occurred_at > now + timedelta(minutes=5):
        raise ValidationError({"occurred_at": [MSG_FUTURE]})
    with transaction.atomic():
        lead = Lead.objects.select_for_update().get(pk=lead.pk)
        _require_open(lead)
        if lead.status == L.WAITING and not outcome:
            raise ValidationError({"outcome": [MSG_OUTCOME]})
        interaction = Interaction.objects.create(
            lead=lead, type=type, occurred_at=occurred_at, notes=(notes or "").strip(), outcome=outcome or "", created_by=actor
        )
        record(actor, lead, "interaction", to_value=type, comment=(notes or "").strip()[:200])
        if lead.first_contacted_at is None or occurred_at < lead.first_contacted_at:
            lead.first_contacted_at = occurred_at
        if lead.last_contacted_at is None or occurred_at > lead.last_contacted_at:
            lead.last_contacted_at = occurred_at
        if lead.status == L.NEW:
            lead.status = L.CONTACTED
            record(actor, lead, "contacted", from_value=L.NEW, to_value=L.CONTACTED)
        if outcome:
            _apply_outcome(lead, actor, outcome, next_follow_up, reason_id, note)
        lead.save()
    return lead, interaction


def set_outcome(actor, lead, *, outcome, next_follow_up=None, reason_id=None, note=""):
    with transaction.atomic():
        lead = Lead.objects.select_for_update().get(pk=lead.pk)
        _require_open(lead)
        if lead.status == L.NEW:
            raise ValidationError({"detail": MSG_FIRST_CONTACT})
        _apply_outcome(lead, actor, outcome, next_follow_up, reason_id, note)
        lead.save()
    return lead


def reopen(actor, lead, note):
    note = (note or "").strip()
    with transaction.atomic():
        lead = Lead.objects.select_for_update().get(pk=lead.pk)
        if lead.archived_at:
            raise ValidationError({"detail": MSG_ARCHIVED})
        if lead.status != L.REJECTED:
            raise ValidationError({"detail": MSG_REOPEN_STATE})
        if not note:
            raise ValidationError({"note": [MSG_REOPEN_NOTE]})
        lead.status = L.CONTACTED
        lead.rejection_reason = None
        lead.rejection_note = ""
        lead.rejected_at = None
        lead.save()
        record(actor, lead, "reopened", from_value=L.REJECTED, to_value=L.CONTACTED, comment=note[:300])
    if lead.assigned_to_id and lead.assigned_to_id != actor.pk:
        notify(lead.assigned_to, "lead_reopened", link=link(lead), actor=actor.full_name, ref=lead.ref, name=lead.company_name)
    return lead


def archive(actor, lead, reason):
    reason = (reason or "").strip()
    if lead.archived_at:
        raise ValidationError({"detail": MSG_ARCHIVE_DONE})
    if not reason:
        raise ValidationError({"reason": [MSG_ARCHIVE_REASON]})
    with transaction.atomic():
        lead.archived_at = timezone.now()
        lead.archive_reason = reason
        lead.save()
        record(actor, lead, "archived", comment=reason[:300])
    return lead


def restore(actor, lead):
    if not lead.archived_at:
        raise ValidationError({"detail": MSG_RESTORE})
    with transaction.atomic():
        lead.archived_at = None
        lead.archive_reason = ""
        lead.save()
        record(actor, lead, "restored")
    return lead


MSG_SKIP_STATE = "Only a qualified lead can skip the quotation."
MSG_SKIP_OPEN = "This lead already has a quotation in progress."
MSG_SKIP_DONE = "The quotation was already skipped for this lead."


def skip_quotation(actor, lead, note=""):
    """Qualified -> straight to the contract step. Recorded, so the trail shows the quotation was a decision, not an omission."""
    note = (note or "").strip()[:300]
    with transaction.atomic():
        lead = Lead.objects.select_for_update().get(pk=lead.pk)
        if lead.archived_at:
            raise ValidationError({"detail": MSG_ARCHIVED})
        if lead.status != L.QUALIFIED:
            raise ValidationError({"detail": MSG_SKIP_STATE})
        if lead.skipped_quotation_at:
            raise ValidationError({"detail": MSG_SKIP_DONE})
        if lead.quotations.filter(status__in=["requested", "in_preparation", "in_review", "changes_requested", "signed", "sent", "waiting"]).exists():
            raise ValidationError({"detail": MSG_SKIP_OPEN})
        lead.skipped_quotation_at = timezone.now()
        lead.skipped_quotation_by = actor
        lead.save()
        record(actor, lead, "quotation_skipped", comment=note)
    return lead
