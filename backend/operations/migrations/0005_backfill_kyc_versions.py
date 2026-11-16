"""Documents already filed against checklist items become versions, oldest first, so every existing client has a history from day one.
The newest version carries the item's current state (verified or not). Reversible: going back removes the versions this created."""
from django.db import migrations


def forwards(apps, schema_editor):
    Item = apps.get_model("operations", "ChecklistItem")
    Version = apps.get_model("operations", "ChecklistItemVersion")
    Attachment = apps.get_model("files", "Attachment")
    CT = apps.get_model("contenttypes", "ContentType")
    ct = CT.objects.filter(app_label="operations", model="checklistitem").first()
    if ct is None:
        return
    for item in Item.objects.all().iterator():
        files = list(Attachment.objects.filter(content_type=ct, object_id=item.pk, archived_at__isnull=True).order_by("id"))
        for n, a in enumerate(files, start=1):
            latest = n == len(files)
            verified = latest and item.status == "verified"
            Version.objects.create(
                item=item, number=n, attachment=a, filename=a.original_name[:255], uploaded_by_id=a.uploaded_by_id,
                state="verified" if verified else ("uploaded" if latest else "superseded"),
                verified_by_id=item.verified_by_id if verified else None, verified_at=item.verified_at if verified else None,
            )


def backwards(apps, schema_editor):
    apps.get_model("operations", "ChecklistItemVersion").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("operations", "0004_kyc_versions_and_staffing"), ("files", "0001_initial"), ("contenttypes", "0002_remove_content_type_name")]
    operations = [migrations.RunPython(forwards, backwards)]
