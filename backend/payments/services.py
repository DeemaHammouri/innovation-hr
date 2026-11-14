"""Instalment schedules, payments, reversals, balances and statements."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Case, Count, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from audit.models import record
from clients.models import Client
from notifications.service import notify

from .models import Instalment, Payment

MSG_STATE = "That can't be done in the current state."
MSG_NO_INSTALMENTS = "Add at least one instalment."
MSG_TOO_MANY = "A schedule can have up to 36 instalments."
MSG_DATE = "Choose a valid due date."
MSG_AMOUNT = "Enter an amount greater than zero."
MSG_CURRENCY = "Enter a 3-letter currency code, such as JOD."
MSG_CURRENCY_MIX = "This client already has instalments in another currency."
MSG_NOTE_LONG = "Keep this under 200 characters."
MSG_HAS_PAYMENTS = "This instalment already has payments, so it can't be changed."
MSG_CANCEL_REASON = "Write why you are cancelling this instalment."
MSG_CANCEL_PAID = "Reverse the payments on this instalment before cancelling it."
MSG_PAY_DATE = "Choose the date the money was received. It can't be in the future."
MSG_PAY_OVER = "That is more than the balance still due on this instalment."
MSG_METHOD = "Choose how it was paid."
MSG_REFERENCE_LONG = "Keep the reference under 100 characters."
MSG_REVERSAL_REASON = "Write why this payment is being reversed."
MSG_ALREADY_REVERSED = "This payment has already been reversed."
MSG_REVERSE_REVERSAL = "A reversal can't be reversed. Record the payment again instead."

TWO = Decimal("0.01")
MAX_AMOUNT = Decimal("9999999999.99")
STATUSES = ("expected", "partially_paid", "paid", "overdue", "cancelled")

SIGNED = Case(
    When(payments__kind="payment", then=F("payments__amount")),
    When(payments__kind="reversal", then=-F("payments__amount")),
    default=Value(Decimal("0")),
    output_field=DecimalField(max_digits=14, decimal_places=2),
)


def with_paid(qs):
    """Annotate instalments with the net amount paid (payments minus reversals)."""
    return qs.annotate(paid=Coalesce(Sum(SIGNED), Value(Decimal("0")), output_field=DecimalField(max_digits=14, decimal_places=2)), n_payments=Count("payments"))


def status_of(inst, paid, today):
    """Cancelled / Paid / Overdue / Partially paid / Expected. Overdue wins over Partially paid once the due date has passed."""
    if inst.cancelled_at:
        return "cancelled"
    if paid >= inst.amount:
        return "paid"
    if inst.due_date < today:
        return "overdue"
    return "partially_paid" if paid > 0 else "expected"


def _money(raw, message=MSG_AMOUNT):
    try:
        value = Decimal(str(raw).strip()).quantize(TWO)
    except (InvalidOperation, ValueError, AttributeError):
        raise ValidationError({"amount": message})
    if not value.is_finite() or value <= 0 or value > MAX_AMOUNT:
        raise ValidationError({"amount": message})
    return value


def _date(raw, field, message):
    try:
        return date.fromisoformat(str(raw)[:10])
    except (ValueError, TypeError):
        raise ValidationError({field: message})


def _currency(raw):
    code = str(raw or "JOD").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValidationError({"currency": MSG_CURRENCY})
    return code


def _row_errors(rows, field, message, index):
    return ValidationError({"instalments": [{field: message} if i == index else {} for i in range(len(rows))]})


# ---------- schedule ----------
def create_schedule(actor, client, data):
    rows = data.get("instalments")
    if not isinstance(rows, list) or not rows:
        raise ValidationError({"instalments": MSG_NO_INSTALMENTS})
    if len(rows) > 36:
        raise ValidationError({"instalments": MSG_TOO_MANY})
    currency = _currency(data.get("currency"))
    clean = []
    for i, row in enumerate(rows):
        row = row if isinstance(row, dict) else {}
        try:
            due = date.fromisoformat(str(row.get("due_date"))[:10])
        except (ValueError, TypeError):
            raise _row_errors(rows, "due_date", MSG_DATE, i)
        try:
            amount = _money(row.get("amount"))
        except ValidationError:
            raise _row_errors(rows, "amount", MSG_AMOUNT, i)
        note = str(row.get("note") or "").strip()
        if len(note) > 200:
            raise _row_errors(rows, "note", MSG_NOTE_LONG, i)
        clean.append((due, amount, note))
    contract = None
    if data.get("contract"):
        contract = client.contracts.filter(pk=data["contract"] if str(data["contract"]).isdigit() else 0).first()
        if contract is None:
            raise ValidationError({"contract": "Choose one of this client's contracts."})
    with transaction.atomic():
        Client.objects.select_for_update().get(pk=client.pk)
        existing = Instalment.objects.filter(client=client, cancelled_at__isnull=True)
        other = existing.exclude(currency=currency).exists()
        if other:
            raise ValidationError({"currency": MSG_CURRENCY_MIX})
        start = (Instalment.objects.filter(client=client).order_by("-number").values_list("number", flat=True).first() or 0) + 1
        made = []
        for offset, (due, amount, note) in enumerate(sorted(clean, key=lambda r: r[0])):
            inst = Instalment.objects.create(client=client, contract=contract, number=start + offset, due_date=due, amount=amount, currency=currency, note=note, created_by=actor)
            record(actor, inst, "created", to_value=f"{amount} {currency}", comment=f"Due {due.isoformat()}")
            made.append(inst)
    return made


def update_instalment(actor, inst, data):
    with transaction.atomic():
        inst = Instalment.objects.select_for_update().get(pk=inst.pk)
        if inst.cancelled_at:
            raise ValidationError({"detail": MSG_STATE})
        if inst.payments.exists():
            raise ValidationError({"detail": MSG_HAS_PAYMENTS})
        changed = []
        if "due_date" in data:
            inst.due_date = _date(data["due_date"], "due_date", MSG_DATE)
            changed.append("due_date")
        if "amount" in data:
            inst.amount = _money(data["amount"])
            changed.append("amount")
        if "note" in data:
            note = str(data["note"] or "").strip()
            if len(note) > 200:
                raise ValidationError({"note": MSG_NOTE_LONG})
            inst.note = note
            changed.append("note")
        if changed:
            inst.save()
            record(actor, inst, "updated", to_value=", ".join(changed))
    return inst


def cancel_instalment(actor, inst, reason):
    reason = str(reason or "").strip()
    if not reason:
        raise ValidationError({"reason": MSG_CANCEL_REASON})
    if len(reason) > 300:
        raise ValidationError({"reason": "Keep this under 300 characters."})
    with transaction.atomic():
        Instalment.objects.select_for_update().get(pk=inst.pk)
        inst = with_paid(Instalment.objects.filter(pk=inst.pk)).get()
        if inst.cancelled_at:
            raise ValidationError({"detail": MSG_STATE})
        if inst.paid > 0:
            raise ValidationError({"detail": MSG_CANCEL_PAID})
        inst.cancelled_at, inst.cancel_reason = timezone.now(), reason
        inst.save()
        record(actor, inst, "cancelled", comment=reason)
    return inst


# ---------- payments ----------
def record_payment(actor, inst, data, today=None):
    today = today or timezone.localdate()
    amount = _money(data.get("amount"))
    received = _date(data.get("received_on"), "received_on", MSG_PAY_DATE)
    if received > today or received < today - timedelta(days=365 * 5):
        raise ValidationError({"received_on": MSG_PAY_DATE})
    method = data.get("method") or Payment.Method.BANK
    if method not in Payment.Method.values:
        raise ValidationError({"method": MSG_METHOD})
    reference = str(data.get("reference") or "").strip()
    if len(reference) > 100:
        raise ValidationError({"reference": MSG_REFERENCE_LONG})
    note = str(data.get("note") or "").strip()[:300]
    with transaction.atomic():
        Instalment.objects.select_for_update().get(pk=inst.pk)  # serialise payments on one instalment
        locked = with_paid(Instalment.objects.filter(pk=inst.pk)).get()
        if locked.cancelled_at:
            raise ValidationError({"detail": MSG_STATE})
        if amount > locked.amount - locked.paid:
            raise ValidationError({"amount": MSG_PAY_OVER})
        pay = Payment.objects.create(instalment=locked, amount=amount, received_on=received, method=method, reference=reference, note=note, recorded_by=actor)
        record(actor, pay, "created", to_value=f"{amount} {locked.currency}", comment=reference)
        record(actor, locked, "payment_recorded", to_value=f"{amount} {locked.currency}")
    return pay


def reverse_payment(actor, pay, reason, today=None):
    reason = str(reason or "").strip()
    if not reason:
        raise ValidationError({"reason": MSG_REVERSAL_REASON})
    if len(reason) > 300:
        raise ValidationError({"reason": "Keep this under 300 characters."})
    with transaction.atomic():
        Instalment.objects.select_for_update().get(pk=pay.instalment_id)
        pay = Payment.objects.select_related("instalment").get(pk=pay.pk)
        if pay.kind == Payment.Kind.REVERSAL:
            raise ValidationError({"detail": MSG_REVERSE_REVERSAL})
        if Payment.objects.filter(reverses=pay).exists():
            raise ValidationError({"detail": MSG_ALREADY_REVERSED})
        rev = Payment.objects.create(
            instalment=pay.instalment, kind=Payment.Kind.REVERSAL, amount=pay.amount, received_on=today or timezone.localdate(),
            method=pay.method, reverses=pay, reason=reason, recorded_by=actor,
        )
        record(actor, pay, "reversed", to_value=f"{pay.amount} {pay.instalment.currency}", comment=reason)
        record(actor, rev, "created", to_value=f"{pay.amount} {pay.instalment.currency}", comment=reason)
        record(actor, pay.instalment, "payment_reversed", to_value=f"{pay.amount} {pay.instalment.currency}", comment=reason)
    return rev


# ---------- balances ----------
def summarise(instalments, today):
    """Totals over annotated instalments (cancelled ones are left out of every total)."""
    live = [i for i in instalments if not i.cancelled_at]
    total = sum((i.amount for i in live), Decimal("0"))
    paid = sum((min(i.paid, i.amount) for i in live), Decimal("0"))
    overdue = [i for i in live if status_of(i, i.paid, today) == "overdue"]
    upcoming = [i.due_date for i in live if i.paid < i.amount and i.due_date >= today]
    return {
        "total": total, "paid": paid, "balance": total - paid,
        "overdue_amount": sum((i.amount - i.paid for i in overdue), Decimal("0")), "overdue_count": len(overdue),
        "next_due": min(upcoming) if upcoming else None,
    }


def statement(client, today):
    insts = list(with_paid(Instalment.objects.filter(client=client)).select_related("contract"))
    pays = list(Payment.objects.filter(instalment__client=client).select_related("instalment", "recorded_by", "reverses").order_by("received_on", "id"))
    return insts, pays, summarise(insts, today)


# ---------- reminders ----------
def commercial_head():
    return User.objects.filter(is_active=True, department__name="Commercial", role=User.Role.HEAD).first()


def ceo():
    return User.objects.filter(is_active=True, department__name="Administration", role=User.Role.HEAD).first()


def overdue_reminders(today=None):
    """Tell the Commercial head and the CEO once about each instalment that has gone overdue. Idempotent."""
    today = today or timezone.localdate()
    sent = 0
    qs = with_paid(Instalment.objects.filter(cancelled_at__isnull=True, due_date__lt=today)).select_related("client")
    for inst in qs:
        if inst.paid >= inst.amount:
            continue
        for who in (commercial_head(), ceo()):
            sent += bool(notify(who, "payment_overdue", link=f"/payments/{inst.client_id}", dedupe_key=f"payovr:{inst.pk}", ref=inst.client.company_name, name=f"#{inst.number} · {inst.due_date.isoformat()}"))
    return sent
