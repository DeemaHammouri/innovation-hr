"""Tasks created before periods existed: the period is the due date (each was its own period). Reversible (nothing to undo)."""
from django.db import migrations
from django.db.models import F


def forwards(apps, schema_editor):
    apps.get_model("operations", "TaskInstance").objects.filter(period__isnull=True).update(period=F("due_date"))


class Migration(migrations.Migration):
    dependencies = [("operations", "0006_recurrence_versions_and_holidays")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
