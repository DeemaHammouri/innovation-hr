"""CSV import: parse and judge every row (preview), then import the good ones as one batch (confirm). Undo while nobody has contacted them."""
import csv
import io

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from audit.models import AuditEntry, record
from core.access import content_type_for
from core.models import Sequence
from notifications.service import notify

from .models import ImportBatch, Lead, email_key, phone_key
from .services import commercial_head
from .validation import clean_lead_fields

COLUMNS = ["company_name", "contact_name", "phone", "email", "source", "notes"]
ALIASES = {
    "company": "company_name", "company name": "company_name", "companyname": "company_name",
    "contact": "contact_name", "contact name": "contact_name", "contactname": "contact_name", "name": "contact_name",
    "mobile": "phone", "phone number": "phone", "tel": "phone", "telephone": "phone",
    "e-mail": "email", "email address": "email",
}
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 2000

MSG_EXT = "Upload a .csv file. In Excel, choose Save As > CSV UTF-8."
MSG_SIZE = "This file is over 2 MB. Split it into smaller files."
MSG_ENCODING = "We couldn't read this file. Save it as CSV (UTF-8) and try again."
MSG_COLUMNS = "The file needs a company_name column. Download the template to see the format."
MSG_EMPTY = "The file has no rows to import."
MSG_ROWS = "Import up to 2000 rows at a time."
MSG_CHOOSE = "Choose a file to upload."
MSG_UNDO_STATE = "This batch was already undone."
MSG_UNDO_CONTACTED = "Some leads in this batch have already been contacted, so it can't be undone."

TEMPLATE_ROWS = [
    COLUMNS,
    ["Al Noor Trading", "Hassan Ali", "+962 79 123 4567", "hassan@alnoor.example", "Trade fair", "Interested in bookkeeping"],
    ["شركة الأفق", "خالد العتيبي", "0791234568", "", "Referral", ""],
]


def template_csv():
    out = io.StringIO()
    csv.writer(out).writerows(TEMPLATE_ROWS)
    return "﻿" + out.getvalue()  # BOM so Excel opens Arabic text correctly


def _read(upload):
    if upload is None:
        raise ValidationError({"file": [MSG_CHOOSE]})
    if not str(upload.name).lower().endswith(".csv"):
        raise ValidationError({"file": [MSG_EXT]})
    if upload.size > MAX_BYTES:
        raise ValidationError({"file": [MSG_SIZE]})
    raw = upload.read()
    upload.seek(0)
    if b"\x00" in raw:
        raise ValidationError({"file": [MSG_ENCODING]})
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationError({"file": [MSG_ENCODING]})


def _header_map(fields):
    mapping = {}
    for i, name in enumerate(fields or []):
        key = (name or "").strip().lower().replace("_", " ")
        key = ALIASES.get(key, key.replace(" ", "_"))
        if key in COLUMNS and key not in mapping:
            mapping[key] = i
    return mapping


def parse(upload):
    """Judge every row. Returns {file_name, rows, summary}. Nothing is written."""
    text = _read(upload)
    first_line = text.split("\n", 1)[0]
    delimiter = max(",;\t", key=first_line.count) if first_line.strip() else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        raise ValidationError({"file": [MSG_EMPTY]})
    mapping = _header_map(header)
    if "company_name" not in mapping:
        raise ValidationError({"file": [MSG_COLUMNS]})

    raw_rows = []
    for number, cells in enumerate(reader, start=2):  # row 1 is the header, so data starts at 2 like in Excel
        if not any((c or "").strip() for c in cells):
            continue
        raw_rows.append((number, {c: (cells[i] if i < len(cells) else "") for c, i in mapping.items()}))
    if not raw_rows:
        raise ValidationError({"file": [MSG_EMPTY]})
    if len(raw_rows) > MAX_ROWS:
        raise ValidationError({"file": [MSG_ROWS]})

    rows = []
    for number, data in raw_rows:
        cleaned, errors = clean_lead_fields(data)
        rows.append({"row": number, **cleaned, "errors": [{"field": f, "message": m} for f, m in errors.items()], "duplicate_of": None, "duplicate_in_file": None})

    # Duplicates: against leads already in the system (not archived), then against earlier rows of this same file.
    phones = {phone_key(r["phone"]) for r in rows if phone_key(r["phone"])}
    emails = {email_key(r["email"]) for r in rows if email_key(r["email"])}
    existing_phone, existing_email = {}, {}
    if phones or emails:
        for ref, pk, ek in Lead.objects.filter(Q(phone_key__in=phones) | Q(email_key__in=emails), archived_at__isnull=True).values_list("ref", "phone_key", "email_key"):
            if pk:
                existing_phone.setdefault(pk, ref)
            if ek:
                existing_email.setdefault(ek, ref)
    seen_phone, seen_email = {}, {}
    for r in rows:
        pk, ek = phone_key(r["phone"]), email_key(r["email"])
        r["duplicate_of"] = (existing_phone.get(pk) if pk else None) or (existing_email.get(ek) if ek else None)
        if not r["duplicate_of"]:
            r["duplicate_in_file"] = (seen_phone.get(pk) if pk else None) or (seen_email.get(ek) if ek else None)
        if pk:
            seen_phone.setdefault(pk, r["row"])
        if ek:
            seen_email.setdefault(ek, r["row"])
        r["state"] = "error" if r["errors"] else "duplicate" if (r["duplicate_of"] or r["duplicate_in_file"]) else "ok"

    summary = {
        "total": len(rows),
        "ok": sum(r["state"] == "ok" for r in rows),
        "errors": sum(r["state"] == "error" for r in rows),
        "duplicates": sum(r["state"] == "duplicate" for r in rows),
    }
    return {"file_name": str(upload.name)[:200], "rows": rows, "summary": summary}


def confirm(actor, upload, duplicates="skip"):
    """Import the rows that passed. Rows with errors are always skipped; duplicates are skipped unless asked for."""
    parsed = parse(upload)
    take = [r for r in parsed["rows"] if r["state"] == "ok" or (r["state"] == "duplicate" and duplicates == "import")]
    if not take:
        raise ValidationError({"file": ["There is nothing to import. Fix the rows marked in the preview and try again."]})
    now = timezone.now()
    with transaction.atomic():
        batch = ImportBatch.objects.create(
            ref=Sequence.next_ref("IB"), filename=parsed["file_name"], created_by=actor, total_rows=parsed["summary"]["total"],
            imported_count=len(take), skipped_errors=parsed["summary"]["errors"],
            skipped_duplicates=parsed["summary"]["duplicates"] - sum(r["state"] == "duplicate" for r in take),
        )
        refs = Sequence.reserve("LD", len(take))
        leads = [
            Lead(
                ref=ref, created_by=actor, batch=batch, company_name=r["company_name"], contact_name=r["contact_name"], phone=r["phone"],
                email=r["email"], source=r["source"], notes=r["notes"], phone_key=phone_key(r["phone"]), email_key=email_key(r["email"]),
            )
            for ref, r in zip(refs, take)
        ]
        Lead.objects.bulk_create(leads)
        ct = content_type_for(Lead)
        created = {ref: pk for ref, pk in Lead.objects.filter(batch=batch).values_list("ref", "pk")}
        AuditEntry.objects.bulk_create(
            [AuditEntry(actor=actor, content_type=ct, object_id=created[lead.ref], action="imported", to_value=batch.ref, created_at=now) for lead in leads]
        )
        record(actor, batch, "imported", to_value=str(len(take)))
    head = commercial_head()
    if head:
        notify(head, "leads_new", link="/pipeline", count=len(take), name=batch.filename)
    return batch


def undo(actor, batch):
    """Allowed only while none of the batch's leads has been contacted. The leads are archived, not deleted."""
    with transaction.atomic():
        batch = ImportBatch.objects.select_for_update().get(pk=batch.pk)
        if batch.status == ImportBatch.Status.UNDONE:
            raise ValidationError({"detail": MSG_UNDO_STATE})
        if Lead.objects.filter(batch=batch).filter(Q(first_contacted_at__isnull=False) | ~Q(status="new")).exists():
            raise ValidationError({"detail": MSG_UNDO_CONTACTED})
        now = timezone.now()
        leads = list(Lead.objects.filter(batch=batch, archived_at__isnull=True))
        Lead.objects.filter(pk__in=[lead.pk for lead in leads]).update(archived_at=now, archive_reason="Import undone", updated_at=now)
        ct = content_type_for(Lead)
        AuditEntry.objects.bulk_create(
            [AuditEntry(actor=actor, content_type=ct, object_id=lead.pk, action="archived", comment="Import undone", created_at=now) for lead in leads]
        )
        batch.status = ImportBatch.Status.UNDONE
        batch.undone_at = now
        batch.undone_by = actor
        batch.save()
        record(actor, batch, "import_undone", to_value=str(len(leads)))
    return batch
