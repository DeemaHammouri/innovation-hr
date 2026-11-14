from django.db import migrations

DEFAULTS = [
    ("Annual leave", "إجازة سنوية", True, 21, 1),
    ("Sick leave", "إجازة مرضية", True, 14, 2),
    ("Unpaid leave", "إجازة بدون راتب", False, None, 3),
]


def add(apps, schema_editor):
    LeaveType = apps.get_model("hr", "LeaveType")
    if LeaveType.objects.exists():
        return
    for en, ar, paid, days, order in DEFAULTS:
        LeaveType.objects.create(name_en=en, name_ar=ar, paid=paid, annual_days=days, sort_order=order)


class Migration(migrations.Migration):
    dependencies = [("hr", "0001_initial")]
    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
