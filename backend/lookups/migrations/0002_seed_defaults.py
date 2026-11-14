from django.db import migrations

REASONS = [
    ("Price is too high", "السعر مرتفع"),
    ("Chose a competitor", "اختار منافساً"),
    ("No budget right now", "لا توجد ميزانية حالياً"),
    ("Not interested", "غير مهتم"),
    ("Could not be reached", "تعذّر الوصول إليه"),
    ("Other", "أخرى"),
]
SERVICES = [
    ("Bookkeeping", "مسك الدفاتر"),
    ("VAT and tax filing", "الإقرارات الضريبية وضريبة المبيعات"),
    ("Payroll processing", "إعداد الرواتب"),
    ("Financial statements", "القوائم المالية"),
    ("Audit support", "دعم التدقيق"),
]
CHECKLIST = [
    ("Commercial registration", "السجل التجاري", True),
    ("Tax registration certificate", "شهادة التسجيل الضريبي", True),
    ("Owner or partner ID", "هوية المالك أو الشريك", True),
    ("Authorised signatory document", "وثيقة المفوّض بالتوقيع", True),
    ("Company bank details", "بيانات حساب الشركة البنكي", True),
    ("Articles of association", "عقد التأسيس", False),
]


def seed(apps, schema_editor):
    Reason, Service = apps.get_model("lookups", "RejectionReason"), apps.get_model("lookups", "Service")
    Item, Work, Sla = (apps.get_model("lookups", n) for n in ("ChecklistTemplateItem", "WorkHours", "SlaSetting"))
    if not Reason.objects.exists():
        for i, (en, ar) in enumerate(REASONS):
            Reason.objects.create(name_en=en, name_ar=ar, sort_order=i)
    if not Service.objects.exists():
        for i, (en, ar) in enumerate(SERVICES):
            Service.objects.create(name_en=en, name_ar=ar, sort_order=i)
    if not Item.objects.exists():
        for i, (en, ar, required) in enumerate(CHECKLIST):
            Item.objects.create(name_en=en, name_ar=ar, required=required, sort_order=i)
    Work.objects.get_or_create(pk=1)
    Sla.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("lookups", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
