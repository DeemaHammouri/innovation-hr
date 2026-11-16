"""What the client decided after a completed meeting: Confirm, Waiting (with a follow-up date) or Rejection (with a reason).

Confirm starts the contract, prefilled from the signed quotation. Once the contract has been sent to the client the decision is
locked at Confirm: leaving it answers 409 `contract_sent`."""
from datetime import date

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from audit.models import record
from lookups.models import RejectionReason

DECISIONS = ("confirm", "waiting", "rejection")
LOCKED = ("sent", "ceo_review", "signed", "handed_over")
MSG_NO_MEETING = "Complete a meeting with this client before recording their decision."
MSG_CHOICE = "Choose Confirm, Waiting or Rejection."
MSG_DATE = "Choose the follow-up date."
MSG_PAST = "The follow-up date can't be in the past."
MSG_REASON = "Choose why the client said no."
MSG_NOT_YOURS = "Only the Commercial head or the assigned member can record this."


class ContractSent(APIException):
    status_code = 409
    default_code = "contract_sent"
    default_detail = "The contract has already been sent to the client, so the status can't leave Confirm."


def decide(actor, client, data):
    from appointments import services as appts
    from appointments.models import Appointment
    from contracts import services as contracts
    from leads import access as lead_access

    lead = client.lead
    if lead is None or not lead_access.can_pipeline_write(actor, lead):
        raise PermissionDenied(MSG_NOT_YOURS)
    choice = str(data.get("decision") or "")
    if choice not in DECISIONS:
        raise ValidationError({"decision": [MSG_CHOICE]})
    note = str(data.get("note") or "").strip()[:2000]
    follow_up = reason = None
    if choice == "waiting":
        try:
            follow_up = date.fromisoformat(str(data.get("next_follow_up") or ""))
        except ValueError:
            raise ValidationError({"next_follow_up": [MSG_DATE]})
        if follow_up < timezone.localdate():
            raise ValidationError({"next_follow_up": [MSG_PAST]})
    if choice == "rejection":
        reason = RejectionReason.objects.filter(pk=data["reason"] if str(data.get("reason") or "").isdigit() else 0).first()
        if reason is None:
            raise ValidationError({"reason": [MSG_REASON]})
    with transaction.atomic():
        type(client).objects.select_for_update().get(pk=client.pk)
        client.refresh_from_db()
        sent = lead.contracts.filter(status__in=LOCKED).exists()
        if sent and choice != "confirm":
            raise ContractSent()
        if not Appointment.objects.filter(lead=lead, status="done", type__in=["meeting", "follow_up", "visit", "call"]).exists():
            raise ValidationError({"detail": MSG_NO_MEETING})
        contract = None
        if choice == "confirm":
            if not lead.contracts.exclude(status="cancelled").exists():
                contract = contracts.request_contract(actor, lead, note)
            appts.cancel_open_follow_ups(lead, actor, "The client confirmed")
        else:
            for c in lead.contracts.exclude(status__in=("cancelled", "handed_over")):
                contracts.cancel(actor, c, "The client's status changed")
            if choice == "waiting":
                appts.sync_follow_up(lead, actor, follow_up)
            else:
                appts.cancel_open_follow_ups(lead, actor, "The client rejected")
        was = client.decision
        client.decision, client.decision_at, client.decision_by = choice, timezone.now(), actor
        client.decision_follow_up, client.decision_reason, client.decision_note = follow_up, reason, note
        client.save()
        record(actor, client, "decision", from_value=was, to_value=choice, comment=note[:300])
    return client, contract
