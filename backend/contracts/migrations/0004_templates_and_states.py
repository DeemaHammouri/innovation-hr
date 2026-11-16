"""Moves contracts that sat in the retired `meeting_logged` state back to `with_commercial` and seeds one default contract template.

Additive and reversible (the reverse does nothing: a moved contract stays where it is, which is still a valid state)."""
from django.db import migrations

DEFAULT_EN = """SERVICES AGREEMENT

This agreement is made on {date} between Innovation Accounting Solutions ("the Company") and {client} ("the Client"), {country}.

1. Services
{services}

2. Fees
The total fee is {total} {currency}.
Payment terms: {payment_terms}

3. Term
From {start_date} to {end_date}.

4. General
The Client will provide the documents and access the Company needs to deliver the services. Either party may end this agreement with thirty days' written notice. This agreement is governed by the laws of {country}."""

DEFAULT_AR = """اتفاقية خدمات

أُبرمت هذه الاتفاقية بتاريخ {date} بين شركة الابتكار للحلول المحاسبية («الشركة») و{client} («العميل») في {country}.

١. الخدمات
{services}

٢. الأتعاب
إجمالي الأتعاب {total} {currency}.
شروط الدفع: {payment_terms}

٣. المدة
من {start_date} إلى {end_date}.

٤. أحكام عامة
يلتزم العميل بتزويد الشركة بالمستندات والصلاحيات اللازمة لتنفيذ الخدمات. يحق لأي من الطرفين إنهاء الاتفاقية بإشعار كتابي مدته ثلاثون يوماً. تخضع هذه الاتفاقية لقوانين {country}."""


def forwards(apps, schema_editor):
    Contract = apps.get_model("contracts", "Contract")
    Contract.objects.filter(status="meeting_logged").update(status="with_commercial")
    Template = apps.get_model("contracts", "ContractTemplate")
    Template.objects.get_or_create(country="*", defaults={"name_en": "Standard services agreement", "name_ar": "اتفاقية الخدمات القياسية", "body_en": DEFAULT_EN, "body_ar": DEFAULT_AR})


class Migration(migrations.Migration):
    dependencies = [("contracts", "0003_contracttemplate_and_more")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
