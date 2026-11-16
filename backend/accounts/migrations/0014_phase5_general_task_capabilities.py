"""Phase 5: capabilities for general tasks. Additive: new capabilities are created and given to their default roles; going back removes them again."""
from django.db import migrations

from accounts.catalog import CAPABILITIES, SUPER_ADMIN

NEW = ["gtask.access", "gtask.assign_team", "gtask.assign_any"]


def forwards(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Capability = apps.get_model("accounts", "Capability")
    if not Role.objects.exists():
        return
    roles = {r.key: r for r in Role.objects.all()}
    for code in NEW:
        description, defaults = CAPABILITIES[code]
        cap, created = Capability.objects.get_or_create(code=code, defaults={"description": description})
        if created:
            for key in defaults:
                if key in roles:
                    roles[key].capabilities.add(cap)
    if SUPER_ADMIN in roles:
        roles[SUPER_ADMIN].capabilities.set(Capability.objects.all())


def backwards(apps, schema_editor):
    apps.get_model("accounts", "Capability").objects.filter(code__in=NEW).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0013_phase4_task_review_capabilities")]
    operations = [migrations.RunPython(forwards, backwards)]
