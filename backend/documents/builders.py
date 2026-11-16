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


def signed_copy(obj):
    """The uploaded signed copy (the document of record), newest first, or None."""
    from core.access import content_type_for

    return Attachment.objects.filter(content_type=content_type_for(obj), object_id=obj.pk, category="client_signed_copy", archived_at__isnull=True).order_by("-created_at", "-id").first()
