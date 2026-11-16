"""Turn every old monthly company target into a dated target for that month (first day to last day).

If exactly one active Marketing user exists the target is assigned to them; otherwise it stays a team target (no user) so it keeps
working and nothing is lost. Reversible: going back rebuilds one monthly row from each converted range that covers a whole month."""
import calendar
from datetime import date

from django.db import migrations


def forwards(apps, schema_editor):
    Monthly = apps.get_model("leads", "MonthlyTarget")
    Target = apps.get_model("leads", "LeadTarget")
    User = apps.get_model("accounts", "User")
    marketing = list(User.objects.filter(is_active=True, role_ref__key="marketing")[:2])
    owner = marketing[0] if len(marketing) == 1 else None
    for m in Monthly.objects.all():
        first = date(m.year, m.month, 1)
        last = date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])
        Target.objects.get_or_create(user=owner, start_date=first, end_date=last, defaults={"target": m.target, "set_by_id": m.set_by_id})


def backwards(apps, schema_editor):
    Monthly = apps.get_model("leads", "MonthlyTarget")
    Target = apps.get_model("leads", "LeadTarget")
    for t in Target.objects.all():
        if t.start_date.day == 1 and t.end_date.day == calendar.monthrange(t.end_date.year, t.end_date.month)[1] and (t.start_date.year, t.start_date.month) == (t.end_date.year, t.end_date.month):
            Monthly.objects.get_or_create(year=t.start_date.year, month=t.start_date.month, defaults={"target": t.target, "set_by_id": t.set_by_id})


class Migration(migrations.Migration):
    dependencies = [("leads", "0010_lead_target"), ("accounts", "0008_sync_new_capabilities")]
    operations = [migrations.RunPython(forwards, backwards)]
