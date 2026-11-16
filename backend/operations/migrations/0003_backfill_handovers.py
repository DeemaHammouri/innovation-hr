"""Contracts handed over under the old flow have no Handover record. Give each one an accepted Handover and a Project, so that every active
client already in Operation has the same shape as a new one. Nothing about prices is copied. Reversible: going back removes only the
records this migration made (marked by the text in `decision_comment`)."""
from django.db import migrations

MARK = "Created from a contract handed over before handovers existed."


def _ref(apps, prefix):
    Sequence = apps.get_model("core", "Sequence")
    seq, _ = Sequence.objects.get_or_create(prefix=prefix)
    seq.last += 1
    seq.save(update_fields=["last"])
    return f"{prefix}-{seq.last:04d}"


def forwards(apps, schema_editor):
    Contract = apps.get_model("contracts", "Contract")
    Handover = apps.get_model("operations", "Handover")
    Project = apps.get_model("operations", "Project")
    for c in Contract.objects.filter(status="handed_over", client__isnull=False, handover__isnull=True).select_related("lead", "client").order_by("id"):
        h = Handover.objects.create(
            ref=_ref(apps, "HO"), contract=c, client=c.client, status="accepted", prepared_by_id=c.requested_by_id, decision_comment=MARK,
            decided_by_id=c.handed_over_by_id, decided_at=c.handed_over_at, submitted_at=c.handed_over_at,
        )
        Project.objects.create(ref=_ref(apps, "PRJ"), client=c.client, handover=h, name=c.client.company_name, created_by_id=c.handed_over_by_id or c.requested_by_id)


def backwards(apps, schema_editor):
    Handover = apps.get_model("operations", "Handover")
    Project = apps.get_model("operations", "Project")
    legacy = Handover.objects.filter(decision_comment=MARK)
    Project.objects.filter(handover__in=legacy).delete()
    legacy.delete()


class Migration(migrations.Migration):
    dependencies = [("operations", "0002_handover_and_project"), ("contracts", "0005_remove_old_meeting_fields"), ("core", "0003_companyprofile_yearsequence")]
    operations = [migrations.RunPython(forwards, backwards)]
