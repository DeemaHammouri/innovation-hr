"""
The quotation workflow. Every transition checks its own state, so an invalid move is refused here whatever the screen showed.

requested -> in_preparation -> in_review -> signed -> sent -> confirmed | waiting | rejected
                    ^              |
                    +- changes_requested (comment required, starts a new version)
Cancelled (with a reason, Commercial head) is possible from any open state.
"""
import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from audit.models import record
from core.models import Sequence
from lookups.models import RejectionReason, Service
from notifications.service import notify, notify_many

from .models import OPEN, Quotation, QuotationLine, QuotationVersion

MSG_NOT_QUALIFIED = "Only a qualified lead can get a quotation."
MSG_LEAD_ARCHIVED = "This lead is archived."
MSG_SKIPPED = "Quotation was skipped for this lead."
MSG_OPEN_EXISTS = "This lead already has a quotation in progress."
MSG_STATE = "This quotation can't do that in its current state."
MSG_NO_LINES = "Add at least one line before sending this for review."
MSG_VALID_UNTIL = "Choose how long this quotation is valid."
MSG_VALID_PAST = "Choose today or a later date."
MSG_CURRENCY = "Enter a 3-letter currency code, for example JOD."
MSG_LINES_LIMIT = "A quotation can have up to 100 lines."
MSG_DESCRIPTION = "Describe what is being sold."
MSG_DESCRIPTION_LONG = "Keep the description under 300 characters."
MSG_NUMBER = "Enter a number."
MSG_QUANTITY = "Enter a quantity above zero."
MSG_PRICE = "Enter a price of zero or more."
MSG_PERCENT = "Enter a percentage from 0 to 100."
MSG_SERVICE = "Choose a service from the list."
MSG_COMMENT = "Write what needs to change."
MSG_CANCEL_REASON = "Write why you are cancelling this quotation."
MSG_OUTCOME = "Choose what the client decided: confirmed, waiting or rejected."
MSG_FOLLOW_UP = "Choose a follow-up date."
MSG_FOLLOW_UP_PAST = "Choose today or a later date."
MSG_FOLLOW_UP_FAR = "Choose a date within the next year."
MSG_REASON = "Choose why the client said no."
MSG_NOTES_LONG = "Keep the notes under 2000 characters."
MSG_NO_DRAFT = "There is no draft to edit."

TWO = Decimal("0.01")
Q = Quotation.Status


def money(value):
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


def hr_users():
    return User.objects.filter(is_active=True, department__name="HR")


def commercial_head():
    return User.objects.filter(is_active=True, department__name="Commercial", role=User.Role.HEAD).first()


def link(q):
    return f"/quotations/{q.pk}"


def _locked(q):
    return Quotation.objects.select_for_update().select_related("lead", "lead__assigned_to").get(pk=q.pk)


def _require(q, *states):
    if q.status not in states:
        raise ValidationError({"detail": MSG_STATE})


def latest_version(q):
    return q.versions.order_by("-number").first()


def draft_version(q):
    v = latest_version(q)
    return v if v and v.submitted_at is None else None


# ---------- request ----------
def request_quotation(actor, lead, note=""):
    note = (note or "").strip()[:1000]
    if lead.archived_at:
        raise ValidationError({"detail": MSG_LEAD_ARCHIVED})
    if lead.status != "qualified":
        raise ValidationError({"detail": MSG_NOT_QUALIFIED})
    if lead.skipped_quotation_at:
        raise ValidationError({"detail": MSG_SKIPPED})
    try:
        with transaction.atomic():
            if lead.quotations.filter(status__in=OPEN).exists():
                raise ValidationError({"detail": MSG_OPEN_EXISTS})
            q = Quotation.objects.create(ref=Sequence.next_ref("QT"), lead=lead, requested_by=actor, request_note=note)
            record(actor, q, "requested", comment=note[:300])
            record(actor, lead, "quotation_requested", to_value=q.ref)
    except IntegrityError:
        raise ValidationError({"detail": MSG_OPEN_EXISTS})
    notify_many(hr_users(), "request_received", exclude=actor, link=link(q), ref=q.ref, name=lead.company_name)
    return q


# ---------- preparation (HR) ----------
def _copy_lines(src, dst):
    QuotationLine.objects.bulk_create([
        QuotationLine(version=dst, position=l.position, service_id=l.service_id, description=l.description, quantity=l.quantity,
                      unit_price=l.unit_price, discount_percent=l.discount_percent, tax_percent=l.tax_percent, line_total=l.line_total)
        for l in src.lines.all()
    ])


def start_preparing(actor, q):
    """Requested -> In preparation (a first empty draft), or Changes requested -> In preparation (a new version copied from the last)."""
    with transaction.atomic():
        q = _locked(q)
        _require(q, Q.REQUESTED, Q.CHANGES_REQUESTED)
        previous = latest_version(q)
        number = (previous.number if previous else 0) + 1
        if previous:
            v = QuotationVersion.objects.create(quotation=q, number=number, currency=previous.currency, valid_until=previous.valid_until, notes=previous.notes, created_by=actor)
            _copy_lines(previous, v)
            _totals(v)
        else:
            v = QuotationVersion.objects.create(quotation=q, number=number, created_by=actor)
        was = q.status
        q.status = Q.IN_PREPARATION
        q.prepared_by = actor
        q.save()
        record(actor, q, "preparation_started" if number == 1 else "version_started", from_value=was, to_value=str(number))
    return q


def _num(raw, minimum=None, maximum=None, allow_zero=True):
    try:
        d = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None, MSG_NUMBER
    if not d.is_finite():
        return None, MSG_NUMBER
    return d, None


def _clean_line(raw, index):
    errors = {}
    d = raw if isinstance(raw, dict) else {}
    description = str(d.get("description") or "").strip()
    if not description:
        errors["description"] = MSG_DESCRIPTION
    elif len(description) > 300:
        errors["description"] = MSG_DESCRIPTION_LONG
    service = None
    if d.get("service") not in (None, ""):
        service = Service.objects.filter(pk=d.get("service") if str(d.get("service")).isdigit() else 0, is_active=True).first()
        if service is None:
            errors["service"] = MSG_SERVICE
    qty, err = _num(d.get("quantity", 1))
    if err:
        errors["quantity"] = err
    elif qty <= 0 or qty > Decimal("999999"):
        errors["quantity"] = MSG_QUANTITY
    price, err = _num(d.get("unit_price", 0))
    if err:
        errors["unit_price"] = err
    elif price < 0 or price > Decimal("999999999"):
        errors["unit_price"] = MSG_PRICE
    disc, err = _num(d.get("discount_percent", 0) if d.get("discount_percent") not in (None, "") else 0)
    if err:
        errors["discount_percent"] = err
    elif disc < 0 or disc > 100:
        errors["discount_percent"] = MSG_PERCENT
    tax, err = _num(d.get("tax_percent", 0) if d.get("tax_percent") not in (None, "") else 0)
    if err:
        errors["tax_percent"] = err
    elif tax < 0 or tax > 100:
        errors["tax_percent"] = MSG_PERCENT
    if errors:
        return None, errors
    gross = qty * price
    net = gross - gross * disc / 100
    total = money(net + net * tax / 100)
    return QuotationLine(position=index, service=service, description=description, quantity=money(qty), unit_price=money(price),
                         discount_percent=money(disc), tax_percent=money(tax), line_total=total), None


def _totals(v):
    subtotal = discount = tax = Decimal("0")
    for l in v.lines.all():
        gross = l.quantity * l.unit_price
        disc = gross * l.discount_percent / 100
        net = gross - disc
        subtotal += gross
        discount += disc
        tax += net * l.tax_percent / 100
    v.subtotal, v.discount_total, v.tax_total = money(subtotal), money(discount), money(tax)
    v.total = money(subtotal - discount + tax)
    v.save()


def save_draft(actor, q, data):
    """Replace the draft's details and lines in one step. Nothing is half-saved: any problem refuses the whole save."""
    data = data or {}
    problems = {}
    currency = str(data.get("currency") or "JOD").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", currency):
        problems["currency"] = [MSG_CURRENCY]
    notes = str(data.get("notes") or "")
    if len(notes) > 2000:
        problems["notes"] = [MSG_NOTES_LONG]
    valid_until = None
    if data.get("valid_until"):
        try:
            valid_until = date.fromisoformat(str(data["valid_until"])[:10])
        except ValueError:
            problems["valid_until"] = [MSG_VALID_UNTIL]
    raw_lines = data.get("lines") or []
    if not isinstance(raw_lines, list) or len(raw_lines) > 100:
        problems["lines"] = [MSG_LINES_LIMIT]
        raw_lines = []
    lines, line_errors = [], []
    for i, raw in enumerate(raw_lines):
        line, errs = _clean_line(raw, i)
        lines.append(line)
        line_errors.append(errs or {})
    if any(line_errors):
        problems["lines"] = line_errors
    if problems:
        raise ValidationError(problems)
    with transaction.atomic():
        q = _locked(q)
        _require(q, Q.IN_PREPARATION)
        v = draft_version(q)
        if v is None:
            raise ValidationError({"detail": MSG_NO_DRAFT})
        v.currency, v.valid_until, v.notes = currency, valid_until, notes
        v.lines.all().delete()
        for line in lines:
            line.version = v
        QuotationLine.objects.bulk_create(lines)
        _totals(v)
        q.prepared_by = actor
        q.save()
    return q


def submit(actor, q):
    with transaction.atomic():
        q = _locked(q)
        _require(q, Q.IN_PREPARATION)
        v = draft_version(q)
        if v is None:
            raise ValidationError({"detail": MSG_NO_DRAFT})
        if not v.lines.exists():
            raise ValidationError({"lines": [MSG_NO_LINES]})
        if not v.valid_until:
            raise ValidationError({"valid_until": [MSG_VALID_UNTIL]})
        if v.valid_until < timezone.localdate():
            raise ValidationError({"valid_until": [MSG_VALID_PAST]})
        v.submitted_at = timezone.now()
        v.save()
        q.status = Q.IN_REVIEW
        q.review_comment = ""
        q.save()
        record(actor, q, "submitted", from_value=Q.IN_PREPARATION, to_value=str(v.number))
    head = commercial_head()
    if head:
        notify(head, "quotation_review", link=link(q), ref=q.ref, name=q.lead.company_name)
    return q


# ---------- review (Commercial head) ----------
def request_changes(actor, q, comment):
    comment = (comment or "").strip()
    if not comment:
        raise ValidationError({"comment": [MSG_COMMENT]})
    with transaction.atomic():
        q = _locked(q)
        _require(q, Q.IN_REVIEW)
        q.status = Q.CHANGES_REQUESTED
        q.review_comment = comment[:2000]
        q.save()
        record(actor, q, "changes_requested", from_value=Q.IN_REVIEW, to_value=Q.CHANGES_REQUESTED, comment=comment[:300])
    team = [q.prepared_by] if q.prepared_by_id and q.prepared_by.is_active else list(hr_users())
    notify_many(team, "returned", exclude=actor, link=link(q), ref=q.ref, name=q.lead.company_name)
    return q


def sign(actor, q):
    """The Commercial head signs the submitted version. Signer and time are stored with the quotation."""
    with transaction.atomic():
        q = _locked(q)
        _require(q, Q.IN_REVIEW)
        v = latest_version(q)
        q.status = Q.SIGNED
        q.signed_by = actor
        q.signed_at = timezone.now()
        q.signed_version = v.number
        q.save()
        record(actor, q, "signed", from_value=Q.IN_REVIEW, to_value=str(v.number))
    notify_many([q.prepared_by, q.requested_by], "signed", exclude=actor, link=link(q), ref=q.ref, name=q.lead.company_name)
    return q


# ---------- after signing (Commercial pipeline) ----------
def mark_sent(actor, q):
    with transaction.atomic():
        q = _locked(q)
        _require(q, Q.SIGNED)
        q.status = Q.SENT
        q.sent_at = timezone.now()
        q.save()
        record(actor, q, "sent", from_value=Q.SIGNED, to_value=Q.SENT)
    return q


def set_outcome(actor, q, *, outcome, next_follow_up=None, reason_id=None, note=""):
    if outcome not in ("confirmed", "waiting", "rejected"):
        raise ValidationError({"outcome": [MSG_OUTCOME]})
    reason = None
    if outcome == "waiting":
        if not next_follow_up:
            raise ValidationError({"next_follow_up": [MSG_FOLLOW_UP]})
        today = timezone.localdate()
        if next_follow_up < today:
            raise ValidationError({"next_follow_up": [MSG_FOLLOW_UP_PAST]})
        if next_follow_up > today + timedelta(days=366):
            raise ValidationError({"next_follow_up": [MSG_FOLLOW_UP_FAR]})
    if outcome == "rejected":
        reason = RejectionReason.objects.filter(pk=reason_id, is_active=True).first() if reason_id else None
        if reason is None:
            raise ValidationError({"rejection_reason": [MSG_REASON]})
    with transaction.atomic():
        q = _locked(q)
        _require(q, Q.SENT, Q.WAITING)
        was = q.status
        q.status = outcome
        q.next_follow_up = next_follow_up if outcome == "waiting" else None
        q.rejection_reason = reason
        q.rejection_note = (note or "").strip()[:1000] if outcome == "rejected" else ""
        q.outcome_at = timezone.now() if outcome != "waiting" else q.outcome_at
        q.save()
        record(actor, q, f"outcome_{outcome}", from_value=was, to_value=outcome, comment=q.rejection_note[:300])
    if outcome in ("confirmed", "rejected"):
        kind = "quotation_confirmed" if outcome == "confirmed" else "quotation_rejected"
        notify_many([commercial_head(), *hr_users()], kind, exclude=actor, link=link(q), actor=actor.full_name, ref=q.ref, name=q.lead.company_name)
    return q


def cancel(actor, q, reason):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": [MSG_CANCEL_REASON]})
    with transaction.atomic():
        q = _locked(q)
        _require(q, *OPEN)
        was = q.status
        q.status = Q.CANCELLED
        q.cancel_reason = reason[:1000]
        q.save()
        record(actor, q, "cancelled", from_value=was, to_value=Q.CANCELLED, comment=reason[:300])
    return q
