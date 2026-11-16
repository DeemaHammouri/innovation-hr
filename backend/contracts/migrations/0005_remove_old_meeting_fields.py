"""Remove the old contract flow's meeting fields and its `meeting_logged` state.

Meetings are now appointments with their own reports (`meetings` app). Nothing reads these fields any more, but a real database may hold
notes written under the old flow, so they are not thrown away: each non-empty one is first copied into the contract's history as a
`meeting_archived` entry. The migration is reversible: going back re-adds the fields and fills them again from those entries."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def archive(apps, schema_editor):
    Contract = apps.get_model("contracts", "Contract")
    AuditEntry = apps.get_model("audit", "AuditEntry")
    ContentType = apps.get_model("contenttypes", "ContentType")
    ct, _ = ContentType.objects.get_or_create(app_label="contracts", model="contract")
    for c in Contract.objects.exclude(meeting_notes="", meeting_date=None).iterator():
        AuditEntry.objects.create(
            actor_id=c.meeting_by_id, content_type=ct, object_id=c.pk, action="meeting_archived",
            to_value=c.meeting_date.isoformat() if c.meeting_date else "", comment=c.meeting_notes[:5000],
        )


def restore(apps, schema_editor):
    Contract = apps.get_model("contracts", "Contract")
    AuditEntry = apps.get_model("audit", "AuditEntry")
    ct = apps.get_model("contenttypes", "ContentType").objects.filter(app_label="contracts", model="contract").first()
    if ct is None:
        return
    # oldest first, so that if a contract was archived twice the latest entry wins
    for e in AuditEntry.objects.filter(content_type=ct, action="meeting_archived").order_by("created_at", "id"):
        fields = {"meeting_notes": e.comment, "meeting_by_id": e.actor_id}
        if e.to_value:
            fields["meeting_date"] = e.to_value
        Contract.objects.filter(pk=e.object_id).update(**fields)


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("contracts", "0004_templates_and_states"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(archive, restore),
        migrations.RemoveField(model_name="contract", name="meeting_by"),
        migrations.RemoveField(model_name="contract", name="meeting_date"),
        migrations.RemoveField(model_name="contract", name="meeting_notes"),
        migrations.RemoveConstraint(model_name="contract", name="contracts_one_open_per_lead"),
        migrations.AddConstraint(
            model_name="contract",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status__in", ["requested", "drafting", "with_commercial", "confirmed", "sent", "ceo_review", "returned", "signed"])),
                fields=("lead",), name="contracts_one_open_per_lead",
            ),
        ),
        migrations.AlterField(
            model_name="contract", name="status",
            field=models.CharField(
                db_index=True, default="requested", max_length=20,
                choices=[
                    ("requested", "Requested"), ("drafting", "Drafting"), ("with_commercial", "With Commercial"), ("confirmed", "Confirmed by Commercial"),
                    ("sent", "Sent to client"), ("ceo_review", "Waiting for the CEO"), ("returned", "Returned to HR"), ("signed", "Signed by CEO"),
                    ("handed_over", "Handed over"), ("cancelled", "Cancelled"),
                ],
            ),
        ),
    ]
