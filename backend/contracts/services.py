"""
The contract workflow. Every transition checks its own state, so an invalid move is refused here whatever the screen showed.

requested -> drafting (HR) -> with_commercial -> confirmed (Commercial head) -> sent (own yearly number) -> ceo_review (client signed)
          ^                         |                                                                         |
          +------- returned <-------+--- (Commercial head returns it to HR with notes) ----- (CEO returns) -----+
ceo_review -> signed (CEO: drawn signature + company stamp, or an uploaded final copy) -> handed_over (HR)
Cancelled (reason, Commercial head) is possible from any open state.
"""
import re
from decimal import Decimal, InvalidOperation

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import User
from audit.models import record
from core.access import content_type_for
from core.models import CompanyProfile, Sequence, YearSequence
from files.models import Attachment
from notifications.service import notify, notify_many

from .models import OPEN, Contract, ContractTemplate, ContractVersion

MSG_NOT_READY = "A contract can start once the quotation is confirmed or skipped."
MSG_OPEN_EXISTS = "This lead already has a contract in progress."
MSG_STATE = "This contract can't do that in its current state."
MSG_NO_DRAFT = "Write the contract text (or upload the draft file) before sending it to Commercial."
MSG_COMMENT = "Write what needs to change."
MSG_CANCEL = "Write why you are cancelling this contract."
MSG_NO_FINAL = "Upload the final signed contract before handing it over."
MSG_NO_COPY = "Upload the signed copy as a PDF or an image."
MSG_ALREADY_SIGNED = "The client has already signed this contract."
MSG_STAMP = "The CEO must upload the company stamp (Company details) before a contract can be signed."

S = Contract.Status
PLACEHOLDER = re.compile(r"\{(client|company|country|date|total|currency|payment_terms|start_date|end_date|services)\}")


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
    return list(User.objects.filter(is_active=True, role_ref__key="ceo"))


def commercial_head():
    return User.objects.filter(is_active=True, department__name="Commercial", is_dept_head=True).first()


def pipeline_users(c):
    who = [c.lead.assigned_to] if c.lead.assigned_to_id and c.lead.assigned_to.is_active else []
    head = commercial_head()
    return who + ([head] if head and head not in who else [])


def files(c, *categories):
    return Attachment.objects.filter(content_type=content_type_for(Contract), object_id=c.pk, archived_at__isnull=True, category__in=categories)


def latest_version(c):
    return c.versions.order_by("-number").first()


def draft_version(c):
    """The version HR is working on: the newest one, if it has not been sent to Commercial yet."""
    v = latest_version(c)
    return v if v and v.submitted_at is None else None


# ---------- country templates ----------
def template_for(country):
    return ContractTemplate.objects.filter(country=country, is_active=True).first() or ContractTemplate.objects.filter(country="*", is_active=True).first()


def _services_text(rows, lang):
    out = []
    for r in rows:
        bits = [r["description"]]
        if r.get("frequency") and r["frequency"] != "once":
            bits.append(r["frequency"])
        if r.get("visits"):
            bits.append(f'{r["visits"]} visits' if lang == "en" else f'{r["visits"]} زيارات')
        out.append("- " + " / ".join(bits) + f' ({r["line_total"]})')
    return "\n".join(out)


def render_template(tpl, *, client, country_name, v):
    """Fill the template's placeholders from the version's data. Unknown braces are left alone."""
    from clients.countries import COUNTRIES

    names = {c[0]: c for c in COUNTRIES}

    def fill(body, lang):
        values = {
            "client": client, "company": CompanyProfile.get().name_en if lang == "en" else CompanyProfile.get().name_ar or CompanyProfile.get().name_en,
            "country": (names.get(country_name) or (None, country_name, country_name))[1 if lang == "en" else 2],
            "date": timezone.localdate().isoformat(), "total": f"{v.total:,.2f}", "currency": v.currency, "payment_terms": v.payment_terms or "-",
            "start_date": v.start_date.isoformat() if v.start_date else "-", "end_date": v.end_date.isoformat() if v.end_date else "-",
            "services": _services_text(v.services, lang),
        }
        return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), body)

    return fill(tpl.body_en, "en"), fill(tpl.body_ar, "ar")


def _prefill(c, actor, quotation):
    """Version 1 of a contract: the signed quotation's services, total, currency and payment terms, in the country's template."""
    v = ContractVersion(contract=c, number=(latest_version(c).number + 1) if latest_version(c) else 1, created_by=actor, currency="JOD")
    if quotation is not None:
        qv = quotation.versions.order_by("-number").first()
        if qv is not None:
            v.currency, v.total, v.payment_terms = qv.currency, qv.total, qv.payment_terms
            v.services = [
                {"description": ln.description, "frequency": ln.frequency, "visits": ln.visits, "quantity": str(ln.quantity), "unit_price": str(ln.unit_price), "line_total": str(ln.line_total)}
                for ln in qv.lines.all()
            ]
    tpl = template_for(c.country)
    c.template = tpl
    v.title = f"{c.lead.company_name}"
    if tpl:
        v.body_en, v.body_ar = render_template(tpl, client=c.lead.company_name, country_name=c.country, v=v)
    v.save()
    return v


# ---------- the flow ----------
def request_contract(actor, lead, note="", *, prefill=True):
    note = (note or "").strip()[:1000]
    if lead.archived_at or lead.status != "qualified":
        raise ValidationError({"detail": MSG_NOT_READY})
    confirmed = lead.quotations.filter(status="confirmed").order_by("-outcome_at", "-id").first()
    if not (lead.skipped_quotation_at or confirmed):
        raise ValidationError({"detail": MSG_NOT_READY})
    client = getattr(lead, "client", None)
    try:
        with transaction.atomic():
            if lead.contracts.filter(status__in=OPEN).exists():
                raise ValidationError({"detail": MSG_OPEN_EXISTS})
            c = Contract.objects.create(
                ref=Sequence.next_ref("CT"), lead=lead, quotation=confirmed, requested_by=actor, request_note=note, country=(client.country if client else "JO"),
            )
            if prefill:
                _prefill(c, actor, confirmed)
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
        if draft_version(c) is None:
            last = latest_version(c)
            if last is None:
                _prefill(c, actor, c.quotation)
            else:  # a returned contract: a new version that starts as a copy of the last one
                fields = {f: getattr(last, f) for f in ("title", "body_en", "body_ar", "currency", "total", "payment_terms", "start_date", "end_date", "services")}
                ContractVersion.objects.create(contract=c, number=last.number + 1, created_by=actor, **fields)
        record(actor, c, "drafting_started" if was == S.REQUESTED else "redrafting_started", from_value=was, to_value=c.status)
    return c


def _date(raw, field):
    if raw in (None, ""):
        return None
    from datetime import date

    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        raise ValidationError({field: ["Use a date like 2026-01-31."]})


def save_draft(actor, c, data):
    """HR edits the working draft: the text in both languages, terms, dates, or switches the template (which refills the text)."""
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.DRAFTING)
        v = draft_version(c)
        if v is None:
            raise ValidationError({"detail": MSG_STATE})
        if "template" in data and data["template"]:
            tpl = ContractTemplate.objects.filter(pk=data["template"] if str(data["template"]).isdigit() else 0, is_active=True).first()
            if tpl is None:
                raise ValidationError({"template": ["Choose a template from the list."]})
            c.template = tpl
            v.body_en, v.body_ar = render_template(tpl, client=c.lead.company_name, country_name=c.country, v=v)
        for f, limit in (("title", 200), ("body_en", 60000), ("body_ar", 60000), ("payment_terms", 4000)):
            if f in data:
                setattr(v, f, str(data[f] or "").strip()[:limit])
        if "start_date" in data:
            v.start_date = _date(data["start_date"], "start_date")
        if "end_date" in data:
            v.end_date = _date(data["end_date"], "end_date")
        if v.start_date and v.end_date and v.end_date < v.start_date:
            raise ValidationError({"end_date": ["The end date can't be before the start date."]})
        if "currency" in data and data["currency"]:
            cur = str(data["currency"]).strip().upper()
            if not re.fullmatch(r"[A-Z]{3}", cur):
                raise ValidationError({"currency": ["Use a three-letter currency code."]})
            v.currency = cur
        if "total" in data:
            try:
                v.total = Decimal(str(data["total"]))
            except (InvalidOperation, ValueError):
                raise ValidationError({"total": ["Enter a number."]})
            if v.total < 0:
                raise ValidationError({"total": ["The total can't be negative."]})
        v.save()
        c.save(update_fields=["template", "updated_at"])
        record(actor, c, "draft_saved", to_value=f"v{v.number}")
    return c


def send_to_commercial(actor, c, note=""):
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.DRAFTING)
        v = draft_version(c)
        has_file = files(c, "draft").exists()
        if v is None or not (v.body_en.strip() or v.body_ar.strip() or has_file):
            raise ValidationError({"detail": MSG_NO_DRAFT})
        v.note, v.submitted_at = (note or "").strip()[:1000], timezone.now()
        v.save()
        c.status, c.returned_comment = S.WITH_COMMERCIAL, ""
        c.save(update_fields=["status", "returned_comment", "updated_at"])
        record(actor, c, "sent_to_commercial", to_value=f"v{v.number}", comment=v.note[:300])
    notify_many(pipeline_users(c), "request_received", exclude=actor, link=link(c), ref=c.ref, name=c.lead.company_name)
    return c


def return_to_hr(actor, c, comment):
    """The Commercial head sends a prepared contract back to HR with notes the preparer will see."""
    comment = (comment or "").strip()
    if not comment:
        raise ValidationError({"comment": [MSG_COMMENT]})
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.WITH_COMMERCIAL)
        c.status, c.returned_comment = S.RETURNED, comment[:2000]
        c.save(update_fields=["status", "returned_comment", "updated_at"])
        record(actor, c, "returned_by_commercial", comment=comment[:300])
    notify_many(hr_users(), "returned", exclude=actor, link=link(c), ref=c.ref, name=c.lead.company_name)
    return c


def confirm(actor, c):
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.WITH_COMMERCIAL)
        c.status, c.confirmed_by, c.confirmed_at = S.CONFIRMED, actor, timezone.now()
        c.save(update_fields=["status", "confirmed_by", "confirmed_at", "updated_at"])
        record(actor, c, "confirmed")
    notify_many(hr_users(), "contract_confirmed", exclude=actor, link=link(c), ref=c.ref, name=c.lead.company_name)
    return c


def notify_client(c, kind):
    client = getattr(c.lead, "client", None)
    if client and client.portal_user_id and client.portal_user.is_active:
        notify(client.portal_user, kind, link="/portal", ref=c.number or c.ref, name=c.lead.company_name)


def send_to_client(actor, c):
    """Issues the contract's own yearly number and makes it visible to the client. From here the client's status is locked at Confirm."""
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.CONFIRMED)
        c.status, c.sent_at = S.SENT, timezone.now()
        c.number = YearSequence.next_number("contract", CompanyProfile.get().contract_prefix, timezone.localdate())
        c.save(update_fields=["status", "sent_at", "number", "updated_at"])
        record(actor, c, "sent", from_value=S.CONFIRMED, to_value=c.number)
    notify_client(c, "contract_sent_client")
    return c


def _client_signed(c, actor, via):
    c.status, c.client_signed_at, c.client_signed_via, c.client_signed_by = S.CEO_REVIEW, timezone.now(), via, actor
    c.submitted_to_ceo_at, c.ceo_comment = c.client_signed_at, ""
    c.save()
    record(actor, c, "client_signed", from_value=S.SENT, to_value=via)
    notify_many(ceo_users(), "contract_review", link=link(c), ref=c.number or c.ref, name=c.lead.company_name)


def client_sign(user, c, signature):
    from quotations.services import read_signature

    png = read_signature(signature)
    with transaction.atomic():
        c = _locked(c)
        if c.client_signed_at:
            raise ValidationError({"detail": MSG_ALREADY_SIGNED})
        _require(c, S.SENT)
        c.client_signature.save("client-signature.png", ContentFile(png), save=False)
        _client_signed(c, user, "portal")
    return c


def _store(c, actor, upload, category):
    from files.views import ALLOWED, clean_name, validate_upload

    if upload is None:
        raise ValidationError({"file": [MSG_NO_COPY]})
    ext = validate_upload(upload)
    if ext not in ("pdf", "png", "jpg", "jpeg"):
        raise ValidationError({"file": [MSG_NO_COPY]})
    Attachment.objects.create(
        file=upload, original_name=clean_name(upload.name), content_type_header=ALLOWED[ext][1], size=upload.size, category=category,
        uploaded_by=actor, content_type=content_type_for(c), object_id=c.pk,
    )


def upload_client_copy(actor, c, upload):
    """Staff upload the copy the client signed on paper: the document of record, and the client's signature."""
    with transaction.atomic():
        c = _locked(c)
        if c.client_signed_at:
            raise ValidationError({"detail": MSG_ALREADY_SIGNED})
        _require(c, S.SENT)
        _store(c, actor, upload, "client_signed_copy")
        _client_signed(c, actor, "upload")
    return c


def ceo_return(actor, c, comment):
    comment = (comment or "").strip()
    if not comment:
        raise ValidationError({"comment": [MSG_COMMENT]})
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.CEO_REVIEW)
        c.status, c.ceo_comment = S.RETURNED, comment[:2000]
        c.returned_comment = comment[:2000]
        c.save(update_fields=["status", "ceo_comment", "returned_comment", "updated_at"])
        record(actor, c, "returned_by_ceo", comment=comment[:300])
    notify_many(list(hr_users()) + pipeline_users(c), "returned", exclude=actor, link=link(c), ref=c.ref, name=c.lead.company_name)
    return c


def ceo_sign(actor, c, signature=None, upload=None):
    """The CEO signs: a drawn signature with the company stamp, or an uploaded final copy that becomes the document of record."""
    from quotations.services import read_signature

    if upload is None and not signature:
        raise ValidationError({"signature": ["Draw your signature, or upload the final signed copy."]})
    png = read_signature(signature) if upload is None else None
    stamp = CompanyProfile.get().stamp
    if upload is None and not stamp:
        raise ValidationError({"stamp": [MSG_STAMP]})
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.CEO_REVIEW)
        if upload is not None:
            _store(c, actor, upload, "final_signed")
            c.signed_via = "upload"
        else:
            c.signature.save("signature.png", ContentFile(png), save=False)
            with stamp.open("rb") as fh:
                c.stamp.save("stamp.png", ContentFile(fh.read()), save=False)
            c.signed_via = "drawn"
        c.status, c.signed_by, c.signed_at = S.SIGNED, actor, timezone.now()
        c.save()
        record(actor, c, "signed", to_value=c.signed_via)
    notify_many(list(hr_users()) + pipeline_users(c), "signed", exclude=actor, link=link(c), ref=c.number or c.ref, name=c.lead.company_name)
    notify_client(c, "contract_signed_client")
    return c


def hand_over(actor, c):
    with transaction.atomic():
        c = _locked(c)
        _require(c, S.SIGNED)
        if c.signed_via != "drawn" and not files(c, "final_signed").exists():
            raise ValidationError({"detail": MSG_NO_FINAL})
        c.status, c.handed_over_by, c.handed_over_at = S.HANDED_OVER, actor, timezone.now()
        c.save(update_fields=["status", "handed_over_by", "handed_over_at", "updated_at"])
        record(actor, c, "handed_over")
        record(actor, c.lead, "contract_handed_over", to_value=c.ref)
        from operations import services as ops

        ops.onboard(actor, c)
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
