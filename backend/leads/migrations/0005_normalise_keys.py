"""Bring the stored keys onto the new rules: phones as E.164, emails lower-case, and one open lead per phone and per email.

Existing duplicates are not deleted. The oldest lead keeps its key; each later duplicate keeps its phone or email text but loses the key,
so it stays in the system and stops matching. The count is printed. The step cannot be undone exactly (the old keys were a different
format), so the reverse does nothing.
"""
from django.db import migrations

from leads.normalize import normalize_email, normalize_phone


def backfill(apps, schema_editor):
    Lead = apps.get_model("leads", "Lead")
    seen_phone, seen_email = set(), set()
    cleared = 0
    for lead in Lead.objects.order_by("id").iterator():
        phone = normalize_phone(lead.phone)
        email = normalize_email(lead.email)
        if lead.archived_at is None:
            if phone and phone in seen_phone:
                phone, cleared = "", cleared + 1
            if email and email in seen_email:
                email, cleared = "", cleared + 1
            if phone:
                seen_phone.add(phone)
            if email:
                seen_email.add(email)
        Lead.objects.filter(pk=lead.pk).update(phone_key=phone, email_key=email, email=email, phone=phone or lead.phone)
    if cleared:
        print(f"  leads: {cleared} duplicate phone/email key(s) cleared on older duplicate leads (the leads themselves are kept)")


class Migration(migrations.Migration):
    dependencies = [("leads", "0004_lead_position_location")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
