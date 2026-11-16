"""Import leads from an Excel (.xlsx) or CSV file: judge every row (preview), then import the good ones as one batch (confirm).
Undo while nobody has contacted them.

Headers are matched in English or Arabic ("Company", "اسم الشركة", or both as "Company / الشركة"). Every row of the file ends up in
the report as ok, error (with the reasons) or duplicate (of a lead already in the system, or of an earlier row of the same file), so
nothing is skipped silently."""
import csv
import io
import re
import unicodedata
import zipfile

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from rest_framework.exceptions import ValidationError

from audit.models import AuditEntry, record
from core.access import content_type_for
from core.models import Sequence
from notifications.service import notify

from .models import ImportBatch, Lead, LeadStatusChange, email_key, phone_key
from .services import commercial_head
from .validation import clean_lead_fields

COLUMNS = ["company_name", "contact_name", "position", "phone", "email", "location", "source", "notes"]
NAMES = {  # canonical column -> accepted header names, English then Arabic
    "company_name": ["company", "company name", "companyname", "organisation", "organization", "اسم الشركة", "الشركة", "المؤسسة"],
    "contact_name": ["name", "contact", "contact name", "contactname", "full name", "الاسم", "اسم", "اسم جهة الاتصال", "جهة الاتصال", "اسم المسؤول"],
    "position": ["position", "job title", "title", "role", "المسمى الوظيفي", "الوظيفة", "المنصب", "المسمى"],
    "phone": ["phone", "phone number", "mobile", "tel", "telephone", "الهاتف", "رقم الهاتف", "الجوال", "رقم الجوال", "الموبايل", "رقم الموبايل"],
    "email": ["email", "e-mail", "email address", "البريد الإلكتروني", "البريد الالكتروني", "البريد", "الايميل", "الإيميل"],
    "location": ["location", "city", "address", "الموقع", "المدينة", "العنوان"],
    "source": ["source", "المصدر"],
    "notes": ["notes", "note", "comments", "ملاحظات", "ملاحظة"],
}
HEADERS = {
    "en": ["Company", "Name", "Position", "Phone", "Email", "Location", "Source", "Notes"],
    "ar": ["اسم الشركة", "الاسم", "المسمى الوظيفي", "الهاتف", "البريد الإلكتروني", "الموقع", "المصدر", "ملاحظات"],
}
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
MAX_UNZIPPED = 60 * 1024 * 1024  # an .xlsx is a zip; refuse one that would unpack to something huge

MSG_EXT = "Upload an Excel (.xlsx) or CSV (.csv) file. Download the template to see the format."
MSG_XLSX = "We couldn't open this Excel file. Check that it is a real .xlsx file (not renamed from another type) and try again."
MSG_SIZE = "This file is over 5 MB. Split it into smaller files."
MSG_ENCODING = "We couldn't read this file. Save it as CSV (UTF-8) and try again."
MSG_COLUMNS = "The file needs a company column (\"Company\" or \"اسم الشركة\"). Download the template to see the format."
MSG_EMPTY = "The file has no rows to import."
MSG_ROWS = "Import up to 5000 rows at a time."
MSG_CHOOSE = "Choose a file to upload."
MSG_UNDO_STATE = "This batch was already undone."
MSG_UNDO_CONTACTED = "Some leads in this batch have already been contacted, so it can't be undone."

SAMPLE = [
    ["Al Noor Trading", "Hassan Ali", "Finance Manager", "+962 79 123 4567", "hassan@alnoor.example", "Amman", "Trade fair", "Interested in bookkeeping"],
    ["شركة الأفق", "خالد العتيبي", "المدير العام", "0791234568", "", "إربد", "إحالة", ""],
]


def _fold(text):
    """Header text in a comparable form: no diacritics, one kind of alef/ya/ta-marbuta, single spaces, lower case."""
    text = unicodedata.normalize("NFKC", str(text or "")).replace("\u0640", "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.translate(str.maketrans("أإآٱىة", "اااايه")).lower().replace("_", " ")
    return re.sub(r"\s+", " ", text).strip(" :*")


LOOKUP = {_fold(alias): col for col, aliases in NAMES.items() for alias in aliases}


def template_csv(lang="en"):
    out = io.StringIO()
    csv.writer(out).writerows([HEADERS["ar" if lang == "ar" else "en"], *SAMPLE])
    return "\ufeff" + out.getvalue()  # BOM so Excel opens Arabic text correctly


def template_xlsx(lang="en"):
    """A workbook with the header row in the chosen language, two sample rows, and a short bilingual instructions sheet."""
    arabic = lang == "ar"
    wb = Workbook()
    ws = wb.active
    ws.title = "Leads" if not arabic else "العملاء المحتملون"
    ws.append(HEADERS["ar" if arabic else "en"])
    for row in SAMPLE:
        ws.append(row)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0B1F4B")
    for col, width in zip("ABCDEFGH", (28, 22, 24, 20, 30, 18, 20, 36)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A2"
    ws.sheet_view.rightToLeft = arabic
    guide = wb.create_sheet("Instructions" if not arabic else "تعليمات")
    guide.sheet_view.rightToLeft = arabic
    lines = [
        ("Company is required. Add a phone or an email for every row.", "اسم الشركة مطلوب. أضف هاتفًا أو بريدًا إلكترونيًا لكل صف."),
        ("Headers can be in English or Arabic. Keep row 1 as the header.", "يمكن أن تكون العناوين بالإنجليزية أو بالعربية. أبقِ الصف الأول للعناوين."),
        ("Up to 5000 rows and 5 MB per file.", "حتى 5000 صف و5 ميجابايت لكل ملف."),
        ("Phones such as 0797707154 are stored as +962797707154. Rows that repeat a lead already in the system are skipped.", "تُحفظ الأرقام مثل 0797707154 بصيغة +962797707154. تُتخطى الصفوف المكررة لعميل موجود."),
    ]
    for en, ar in lines:
        guide.append([ar if arabic else en])
    guide.column_dimensions["A"].width = 110
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _header_map(fields):
    mapping = {}
    for i, name in enumerate(fields or []):
        cell = str(name if name is not None else "")
        for part in [cell, *re.split(r"\s*[/|]\s*", cell)]:
            col = LOOKUP.get(_fold(part))
            if col and col not in mapping:
                mapping[col] = i
                break
    return mapping


def _text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))  # Excel stores 0791234567 typed as a number; keep the digits
    return str(value).strip()


def _read_csv(raw):
    if b"\x00" in raw:
        raise ValidationError({"file": [MSG_ENCODING]})
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationError({"file": [MSG_ENCODING]})
    first_line = text.split("\n", 1)[0]
    delimiter = max(",;\t", key=first_line.count) if first_line.strip() else ","
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


def _read_xlsx(raw):
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if "xl/workbook.xml" not in z.namelist():
                raise ValidationError({"file": [MSG_XLSX]})
            if sum(i.file_size for i in z.infolist()) > MAX_UNZIPPED:
                raise ValidationError({"file": [MSG_SIZE]})
        sheet = load_workbook(io.BytesIO(raw), read_only=True, data_only=True).worksheets[0]
        return [list(r) for r in sheet.iter_rows(values_only=True)]
    except ValidationError:
        raise
    except Exception:
        raise ValidationError({"file": [MSG_XLSX]})


def _read(upload):
    if upload is None:
        raise ValidationError({"file": [MSG_CHOOSE]})
    name = str(upload.name).lower()
    if not (name.endswith(".csv") or name.endswith(".xlsx")):
        raise ValidationError({"file": [MSG_EXT]})
    if upload.size > MAX_BYTES:
        raise ValidationError({"file": [MSG_SIZE]})
    raw = upload.read()
    upload.seek(0)
    return _read_xlsx(raw) if name.endswith(".xlsx") else _read_csv(raw)


def parse(upload):
    """Judge every row. Returns {file_name, rows, summary}. Nothing is written."""
    table = _read(upload)
    if not table:
        raise ValidationError({"file": [MSG_EMPTY]})
    mapping = _header_map(table[0])
    if "company_name" not in mapping:
        raise ValidationError({"file": [MSG_COLUMNS]})

    raw_rows = []
    for number, cells in enumerate(table[1:], start=2):  # row 1 is the header, so data starts at 2 like in Excel
        if not any(_text(c) for c in cells):
            continue
        raw_rows.append((number, {c: _text(cells[i]) if i < len(cells) else "" for c, i in mapping.items()}))
    if not raw_rows:
        raise ValidationError({"file": [MSG_EMPTY]})
    if len(raw_rows) > MAX_ROWS:
        raise ValidationError({"file": [MSG_ROWS]})

    rows = []
    for number, data in raw_rows:
        cleaned, errors = clean_lead_fields(data)
        rows.append({"row": number, **cleaned, "errors": [{"field": f, "message": m} for f, m in errors.items()], "duplicate_of": None, "duplicate_in_file": None})

    # Duplicates: against open leads already in the system, then against earlier rows of this same file.
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
        if not r["errors"]:  # a row that is itself rejected must not shadow a later good row
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


def _report(rows):
    """Every row that did not come in, with the reason: the full skip report kept on the batch."""
    return [
        {"row": r["row"], "state": r["state"], "company_name": r["company_name"], "phone": r["phone"], "email": r["email"],
         "errors": r["errors"], "duplicate_of": r["duplicate_of"], "duplicate_in_file": r["duplicate_in_file"]}
        for r in rows if r["state"] != "ok"
    ]


def confirm(actor, upload, duplicates="skip"):
    """Import the rows that passed. Rows with errors and duplicates are always skipped, and listed in the batch's skip report.
    (`duplicates` is accepted for old callers and ignored: the database allows one open lead per phone and per email.)"""
    for attempt in range(2):
        parsed = parse(upload)
        take = [r for r in parsed["rows"] if r["state"] == "ok"]
        if not take:
            raise ValidationError({"file": ["There is nothing to import. Fix the rows marked in the preview and try again."]})
        try:
            return _write(actor, parsed, take)
        except IntegrityError:
            # Someone added one of these leads between the preview and now. Judge the rows again; the clash is now a duplicate row.
            if attempt:
                raise ValidationError({"file": ["Another import changed these leads while this one ran. Try again."]})
            upload.seek(0)


def _write(actor, parsed, take):
    now = timezone.now()
    with transaction.atomic():
        batch = ImportBatch.objects.create(
            ref=Sequence.next_ref("IB"), filename=parsed["file_name"], created_by=actor, total_rows=parsed["summary"]["total"],
            imported_count=len(take), skipped_errors=parsed["summary"]["errors"], skipped_duplicates=parsed["summary"]["duplicates"],
            skip_report=_report(parsed["rows"]),
        )
        refs = Sequence.reserve("LD", len(take))
        leads = [
            Lead(
                ref=ref, created_by=actor, batch=batch, company_name=r["company_name"], contact_name=r["contact_name"], position=r["position"],
                phone=phone_key(r["phone"]) or r["phone"], email=email_key(r["email"]), location=r["location"], source=r["source"], notes=r["notes"],
                phone_key=phone_key(r["phone"]), email_key=email_key(r["email"]),
            )
            for ref, r in zip(refs, take)
        ]
        Lead.objects.bulk_create(leads)
        ct = content_type_for(Lead)
        created = {ref: pk for ref, pk in Lead.objects.filter(batch=batch).values_list("ref", "pk")}
        AuditEntry.objects.bulk_create(
            [AuditEntry(actor=actor, content_type=ct, object_id=created[lead.ref], action="imported", to_value=batch.ref, created_at=now) for lead in leads]
        )
        LeadStatusChange.objects.bulk_create(
            [LeadStatusChange(lead_id=created[lead.ref], from_status="", to_status="new", changed_by=actor, changed_at=now, note=batch.ref) for lead in leads]
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
