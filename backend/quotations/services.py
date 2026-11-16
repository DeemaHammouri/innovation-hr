"""
The quotation workflow. Every transition checks its own state, so an invalid move is refused here whatever the screen showed.

requested (HR head may hand it to one HR person) -> in_preparation -> in_review -> signed -> sent -> confirmed | waiting | rejected
                    ^              |
                    +- changes_requested (comment required, starts a new version)
Cancelled (with a reason, Commercial head) is possible from any open state.

Signing needs the head's drawn signature and the company stamp. Sending issues the number PREFIX/YYYY/M/NNNN (one counter per year,
taken in the same transaction, so no gaps and no duplicates). The client then signs on the portal (drawn signature) or staff upload the
signed copy, which becomes the document of record; either one records the client's acceptance (confirmed).
"""
import base64
import binascii
import io
import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import User
from audit.models import record
from core.models import CompanyProfile, Sequence, YearSequence
from files.models import Attachment
from lookups.models import RejectionReason, Service
from notifications.service import notify, notify_many

from .models import FREQUENCIES, OPEN, Quotation, QuotationLine, QuotationVersion

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
MSG_SIGNATURE = "Draw your signature first."
MSG_SIGNATURE_BAD = "That signature could not be read. Draw it again."
MSG_STAMP_MISSING = "The company stamp has not been uploaded yet. Ask the CEO to add it in Settings."
MSG_FREQUENCY = "Choose how often the service is done."
MSG_VISITS = "Enter a whole number of visits, or leave it empty."
MSG_PAYMENT_TERMS = "Keep the payment terms under 2000 characters."
MSG_ASSIGNEE = "Choose a person from HR."
MSG_NOT_YOURS = "This quotation was handed to someone else in HR."
MSG_COPY = "Choose the signed copy (PDF, PNG or JPG)."
MSG_ALREADY_SIGNED = "The client has already signed this quotation."

TWO = Decimal("0.01")
Q = Quotation.Status


def money(value):
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


def hr_users():
    return User.objects.filter(is_active=True, department__name="HR")


def commercial_head():
    return User.objects.filter(is_active=True, department__name="Commercial", is_dept_head=True).first()


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
                      unit_price=l.unit_price, discount_percent=l.discount_percent, tax_percent=l.tax_percent, line_total=l.line_total,
                      frequency=l.frequency, visits=l.visits)
        for l in src.lines.all()
    ])


def assign(actor, q, user_id):
    """The HR head hands a quotation that is waiting for preparation (or was returned) to one HR person."""
    person = hr_users().filter(pk=user_id if str(user_id or "").isdigit() else 0).first()
    if person is None:
        raise ValidationError({"assigned_to": [MSG_ASSIGNEE]})
    with transaction.atomic():
        q = _locked(q)
        _require(q, Q.REQUESTED, Q.CHANGES_REQUESTED)
        was = q.assigned_to_id
        q.assigned_to = person
        q.save()
        record(actor, q, "assigned", from_value=str(was or ""), to_value=person.full_name)
    if person.pk != actor.pk:
        notify(person, "quotation_assigned", link=link(q), ref=q.ref, name=q.lead.company_name)
    return q


def start_preparing(actor, q):
    """Requested -> In preparation (a first empty draft), or Changes requested -> In preparation (a new version copied from the last).

    If the HR head handed it to someone, only that person (or the head) may start it."""
    with transaction.atomic():
        q = _locked(q)
        _require(q, Q.REQUESTED, Q.CHANGES_REQUESTED)
        if q.assigned_to_id and q.assigned_to_id != actor.pk and not actor.has_capability("quotation.assign"):
            raise PermissionDenied(MSG_NOT_YOURS)
        previous = latest_version(q)
        number = (previous.number if previous else 0) + 1
        if previous:
            v = QuotationVersion.objects.create(quotation=q, number=number, currency=previous.currency, valid_until=previous.valid_until, notes=previous.notes, payment_terms=previous.payment_terms, created_by=actor)
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
    frequency = str(d.get("frequency") or "once")
    if frequency not in dict(FREQUENCIES):
        errors["frequency"] = MSG_FREQUENCY
    visits = None
    if d.get("visits") not in (None, ""):
        raw_visits = str(d.get("visits")).strip()
        if not raw_visits.isdigit() or int(raw_visits) > 9999:
            errors["visits"] = MSG_VISITS
        else:
            visits = int(raw_visits)
    if errors:
        return None, errors
    gross = qty * price
    net = gross - gross * disc / 100
    total = money(net + net * tax / 100)
    return QuotationLine(position=index, service=service, description=description, quantity=money(qty), unit_price=money(price),
                         discount_percent=money(disc), tax_percent=money(tax), line_total=total, frequency=frequency, visits=visits), None


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
    payment_terms = str(data.get("payment_terms") or "").strip()
    if len(payment_terms) > 2000:
        problems["payment_terms"] = [MSG_PAYMENT_TERMS]
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
        v.currency, v.valid_until, v.notes, v.payment_terms = currency, valid_until, notes, payment_terms
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


def read_signature(raw):
    """A drawn signature arrives as a PNG data URL (from the canvas). Returns the PNG bytes, or raises a clean error."""
    if not raw:
        raise ValidationError({"signature": [MSG_SIGNATURE]})
    text = raw.decode("latin-1") if isinstance(raw, bytes) else str(raw)
    if text.startswith("data:"):
        head, _, text = text.partition(",")
        if "image/png" not in head or "base64" not in head:
            raise ValidationError({"signature": [MSG_SIGNATURE_BAD]})
    try:
        data = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        raise ValidationError({"signature": [MSG_SIGNATURE_BAD]})
    if not data.startswith(b"\x89PNG") or len(data) > 400_000:
        raise ValidationError({"signature": [MSG_SIGNATURE_BAD]})
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data)).convert("RGBA")
        if img.width > 2000 or img.height > 1000:
            raise ValidationError({"signature": [MSG_SIGNATURE_BAD]})
        # an empty canvas is not a signature: some pixel must be both visible and not white
        if not any(a > 20 and (r < 235 or g < 235 or b < 235) for r, g, b, a in img.getdata()):
            raise ValidationError({"signature": [MSG_SIGNATURE]})
    except ValidationError:
        raise
    except Exception:
        raise ValidationError({"signature": [MSG_SIGNATURE_BAD]})
    return data


def sign(actor, q, signature):
    """The Commercial head signs the submitted version with a drawn signature and the company stamp. Signer, time, signature and a
    copy of the stamp are stored with the quotation."""
    png = read_signature(signature)
    stamp = CompanyProfile.get().stamp
    if not stamp:
        raise ValidationError({"stamp": [MSG_STAMP_MISSING]})
    with transaction.atomic():
        q = _locked(q)
        _require(q, Q.IN_REVIEW)
        v = latest_version(q)
        q.status = Q.SIGNED
        q.signed_by = actor
        q.signed_at = timezone.now()
        q.signed_version = v.number
        q.signature.save("signature.png", ContentFile(png), save=False)
        with stamp.open("rb") as fh:
            q.stamp.save("stamp.png", ContentFile(fh.read()), save=False)
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
        # Taken here, in the same transaction as the status change: if anything below fails, the number goes back too.
        q.number = YearSequence.next_number("quotation", CompanyProfile.get().quotation_prefix, timezone.localdate())
        q.save()
        record(actor, q, "sent", from_value=Q.SIGNED, to_value=q.number)
    notify_client(q, "quotation_sent_client")
    return q


def notify_client(q, kind):
    """Tell the client's portal account (if there is one) that something is waiting for them."""
    client = getattr(q.lead, "client", None)
    if client and client.portal_user_id and client.portal_user.is_active:
        notify(client.portal_user, kind, link="/portal", ref=q.number or q.ref, name=q.lead.company_name)


def _confirm_by_client(q, actor, via):
    was = q.status
    q.status = Q.CONFIRMED
    q.client_signed_at = timezone.now()
    q.client_signed_via = via
    q.client_signed_by = actor
    q.outcome_at = q.client_signed_at
    q.next_follow_up = None
    q.save()
    record(actor, q, "client_signed", from_value=was, to_value=via)
    notify_many([commercial_head(), *hr_users(), q.lead.assigned_to], "quotation_confirmed", exclude=actor, link=link(q), actor=actor.full_name, ref=q.ref, name=q.lead.company_name)


def client_sign(user, q, signature):
    """The client signs on the portal with a drawn signature. `q` must belong to the client the user is the portal account of."""
    png = read_signature(signature)
    with transaction.atomic():
        q = _locked(q)
        if q.client_signed_at:
            raise ValidationError({"detail": MSG_ALREADY_SIGNED})
        _require(q, Q.SENT, Q.WAITING)
        q.client_signature.save("client-signature.png", ContentFile(png), save=False)
        _confirm_by_client(q, user, "portal")
    return q


def upload_signed_copy(actor, q, upload):
    """Staff upload the copy the client signed on paper. It is stored as a document of record and records the client's acceptance."""
    from core.access import content_type_for
    from files.views import ALLOWED, clean_name, validate_upload

    if upload is None:
        raise ValidationError({"file": [MSG_COPY]})
    ext = validate_upload(upload)
    if ext not in ("pdf", "png", "jpg", "jpeg"):
        raise ValidationError({"file": [MSG_COPY]})
    with transaction.atomic():
        q = _locked(q)
        _require(q, Q.SENT, Q.WAITING, Q.CONFIRMED)
        if q.status == Q.CONFIRMED and q.client_signed_via == "portal":
            raise ValidationError({"detail": MSG_ALREADY_SIGNED})
        Attachment.objects.create(
            file=upload, original_name=clean_name(upload.name), content_type_header=ALLOWED[ext][1], size=upload.size, category="client_signed_copy",
            uploaded_by=actor, content_type=content_type_for(q), object_id=q.pk,
        )
        if q.status != Q.CONFIRMED:
            _confirm_by_client(q, actor, "upload")
        else:
            record(actor, q, "signed_copy_replaced", to_value=clean_name(upload.name))
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
