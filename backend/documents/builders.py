"""Turn a business record into a Doc. One builder per kind; the renderers never know what a quotation is."""
from decimal import Decimal

from django.utils import timezone

from core.models import CompanyProfile
from files.models import Attachment

from . import model

FREQUENCY = {
    "once": ("Once", "مرة واحدة"), "monthly": ("Monthly", "شهريًا"), "quarterly": ("Every 3 months", "كل 3 أشهر"),
    "semiannual": ("Every 6 months", "كل 6 أشهر"), "annual": ("Yearly", "سنويًا"),
}
LABELS = {
    "number": ("Number", "الرقم"), "date": ("Date", "التاريخ"), "client": ("Client", "العميل"), "contact": ("Contact", "المسؤول"),
    "valid_until": ("Valid until", "صالح حتى"), "currency": ("Currency", "العملة"), "prepared_by": ("Prepared by", "أعدّه"),
    "items": ("Services and cost", "الخدمات والتكلفة"), "payment_terms": ("Payment terms", "شروط الدفع"), "notes": ("Notes", "ملاحظات"),
    "signatures": ("Signatures", "التوقيعات"), "company_sig": ("For the company", "عن الشركة"), "client_sig": ("Client acceptance", "قبول العميل"),
    "subtotal": ("Subtotal", "المجموع قبل الخصم"), "discount": ("Discount", "الخصم"), "tax": ("Tax", "الضريبة"), "total": ("Total", "الإجمالي"),
    "no": ("#", "#"), "description": ("Description", "الوصف"), "frequency": ("How often", "عدد المرات"), "visits": ("Visits", "الزيارات"),
    "qty": ("Qty", "الكمية"), "unit_price": ("Unit price", "سعر الوحدة"), "disc_pct": ("Disc. %", "خصم ٪"), "tax_pct": ("Tax %", "ضريبة ٪"),
    "line_total": ("Total", "المجموع"),
}


def lab(key):
    return LABELS[key]


def money(value, currency=""):
    return f"{Decimal(value):,.2f}{(' ' + currency) if currency else ''}"


def _read(field):
    if not field:
        return None
    with field.open("rb") as fh:
        return fh.read()


def company_pair():
    p = CompanyProfile.get()
    return (p.name_en, p.name_ar)


def local_date(dt):
    return timezone.localtime(dt).strftime("%Y-%m-%d") if dt else ""


def build_quotation(q):
    version = next((v for v in q.versions.all() if v.number == q.signed_version), None) or max(q.versions.all(), key=lambda v: v.number, default=None)
    lead = q.lead
    c = version.currency if version else ""
    meta = [
        (lab("number"), q.number or q.ref), (lab("date"), local_date(q.sent_at or q.created_at)), (lab("client"), lead.company_name),
        (lab("contact"), lead.contact_name or "—"),
    ]
    if version and version.valid_until:
        meta.append((lab("valid_until"), version.valid_until.isoformat()))
    meta += [(lab("currency"), c or "—"), (lab("prepared_by"), q.prepared_by.full_name if q.prepared_by_id else "—")]
    blocks = [model.Heading(lab("items"))]
    if version:
        rows = []
        for i, l in enumerate(version.lines.all(), 1):
            rows.append([str(i), l.description, f"{FREQUENCY.get(l.frequency, FREQUENCY['once'])[0]}", str(l.visits or "—"), f"{l.quantity:g}", money(l.unit_price), f"{l.discount_percent:g}", f"{l.tax_percent:g}", money(l.line_total)])
        blocks.append(model.Table(
            headers=[lab(k) for k in ("no", "description", "frequency", "visits", "qty", "unit_price", "disc_pct", "tax_pct", "line_total")],
            rows=rows, aligns=["center", "start", "start", "center", "end", "end", "end", "end", "end"], widths=[0.6, 3.2, 1.5, 0.9, 0.9, 1.5, 0.9, 0.9, 1.7],
            totals=[(lab("subtotal"), money(version.subtotal, c)), (lab("discount"), "- " + money(version.discount_total, c)), (lab("tax"), money(version.tax_total, c)), (lab("total"), money(version.total, c))],
        ))
        if version.payment_terms:
            blocks += [model.Heading(lab("payment_terms")), model.Para(version.payment_terms)]
        if version.notes:
            blocks += [model.Heading(lab("notes")), model.Para(version.notes)]
    sigs = []
    if q.signed_at:
        sigs.append(model.Signature(lab("company_sig"), name=q.signed_by.full_name if q.signed_by_id else "", when=local_date(q.signed_at), image=_read(q.signature), stamp=_read(q.stamp)))
    if q.client_signed_at:
        note = "" if q.client_signed_via == "portal" else "Signed copy on file / نسخة موقّعة محفوظة"
        sigs.append(model.Signature(lab("client_sig"), name=lead.contact_name or lead.company_name, when=local_date(q.client_signed_at), image=_read(q.client_signature) if q.client_signed_via == "portal" else None, note=note))
    elif q.signed_at:
        sigs.append(model.Signature(lab("client_sig"), name=lead.contact_name or lead.company_name))
    if sigs:
        blocks += [model.Heading(lab("signatures")), model.Signatures(sigs)]
    return model.Doc(
        kind="quotation", title=("Quotation", "عرض سعر"), number=q.number or q.ref, watermark=not q.signed_at, meta=meta, blocks=blocks,
        company=company_pair(), filename=f"quotation-{(q.number or q.ref).replace('/', '-')}",
    )


def signed_copy(obj, *categories):
    """The uploaded copy that is the document of record, newest first, or None. Categories are tried in order (the first that has a file wins)."""
    from core.access import content_type_for

    for cat in categories or ("client_signed_copy",):
        found = Attachment.objects.filter(content_type=content_type_for(obj), object_id=obj.pk, category=cat, archived_at__isnull=True).order_by("-created_at", "-id").first()
        if found:
            return found
    return None


def _paras(text):
    return [model.Para(line) if line.strip() else model.Para(" ", size=4) for line in str(text or "").split(chr(10))]


def build_contract(c, lang="en"):
    """The contract text (English, Arabic or both, as asked) with the signature blocks. Draft until the CEO has signed."""
    from contracts.services import latest_version

    v = latest_version(c)
    lead = c.lead
    cur = v.currency if v else ""
    meta = [
        (lab("number"), c.number or c.ref), (lab("date"), local_date(c.sent_at or c.created_at)), (lab("client"), lead.company_name),
        (("Country", "الدولة"), c.country), (lab("currency"), cur or "—"),
    ]
    blocks = []
    if v:
        if v.services:
            blocks += [model.Heading(lab("items")), model.Table(
                headers=[lab("no"), lab("description"), lab("frequency"), lab("visits"), lab("line_total")],
                rows=[[str(i), r["description"], FREQUENCY.get(r.get("frequency"), FREQUENCY["once"])[0], str(r.get("visits") or "—"), money(r["line_total"])] for i, r in enumerate(v.services, 1)],
                aligns=["center", "start", "start", "center", "end"], widths=[0.6, 4.2, 1.6, 1.0, 1.8], totals=[(lab("total"), money(v.total, cur))],
            )]
        if lang in ("en", "both") and v.body_en.strip():
            blocks += _paras(v.body_en)
        if lang in ("ar", "both") and v.body_ar.strip():
            blocks += _paras(v.body_ar)
    sigs = []
    if c.client_signed_at:
        note = "" if c.client_signed_via == "portal" else "Signed copy on file / نسخة موقّعة محفوظة"
        sigs.append(model.Signature(lab("client_sig"), name=lead.contact_name or lead.company_name, when=local_date(c.client_signed_at), image=_read(c.client_signature) if c.client_signed_via == "portal" else None, note=note))
    else:
        sigs.append(model.Signature(lab("client_sig"), name=lead.contact_name or lead.company_name))
    if c.signed_at:
        note = "Final signed copy on file / النسخة النهائية الموقّعة محفوظة" if c.signed_via == "upload" else ""
        sigs.append(model.Signature(lab("company_sig"), name=c.signed_by.full_name if c.signed_by_id else "", when=local_date(c.signed_at), image=_read(c.signature), stamp=_read(c.stamp), note=note))
    else:
        sigs.append(model.Signature(lab("company_sig")))
    blocks += [model.Heading(lab("signatures")), model.Signatures(sigs)]
    return model.Doc(
        kind="contract", title=("Contract", "عقد"), number=c.number or c.ref, watermark=not c.signed_at, meta=meta, blocks=blocks,
        company=company_pair(), filename=f"contract-{(c.number or c.ref).replace('/', '-')}",
    )


def build_meeting_report(r):
    """A meeting report. It is a draft until the CEO has approved it."""
    appt = r.appointment
    meta = [
        (("Client", "العميل"), r.lead.company_name), (("Meeting", "الاجتماع"), appt.title), (("Held on", "عُقد في"), r.held_on.isoformat()),
        (("Written by", "كتبه"), r.author.full_name),
    ]
    blocks = []
    for key, pair in (("attendees", ("Attendees", "الحضور")), ("summary", ("What was discussed", "ما جرى في الاجتماع")), ("decisions", ("Decisions", "القرارات")), ("next_steps", ("Next steps", "الخطوات التالية"))):
        text = getattr(r, key)
        if text.strip():
            blocks += [model.Heading(pair), *_paras(text)]
    sigs = []
    if r.signed_at:
        sigs.append(model.Signature(("Commercial", "المبيعات"), name=r.signed_by.full_name if r.signed_by_id else "", when=local_date(r.signed_at), image=_read(r.signature), stamp=_read(r.stamp)))
    else:
        sigs.append(model.Signature(("Commercial", "المبيعات")))
    if r.ceo_at and r.status == "approved":
        sigs.append(model.Signature(("Approved by the CEO", "اعتماد المدير التنفيذي"), name=r.ceo_by.full_name if r.ceo_by_id else "", when=local_date(r.ceo_at)))
    else:
        sigs.append(model.Signature(("Approved by the CEO", "اعتماد المدير التنفيذي")))
    blocks += [model.Heading(lab("signatures")), model.Signatures(sigs)]
    ref = f"MR-{r.pk:05d}"
    return model.Doc(kind="meeting_report", title=("Meeting report", "تقرير اجتماع"), number=ref, watermark=r.status != "approved", meta=meta, blocks=blocks, company=company_pair(), filename=f"meeting-report-{ref}")
