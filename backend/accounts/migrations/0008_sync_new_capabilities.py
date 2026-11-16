"""Phase 2 added capabilities (appointments, leads dashboard and target). Existing installs get them here: a capability that does not
exist yet is created and attached to its default roles; anything an administrator already granted or removed is left alone.
Safe to run on a fresh database (it does nothing until roles exist) and to reverse (nothing to undo)."""
from django.db import migrations

from accounts.catalog import CAPABILITIES, SUPER_ADMIN


def forwards(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Capability = apps.get_model("accounts", "Capability")
    if not Role.objects.exists():
        return
    roles = {r.key: r for r in Role.objects.all()}
    for code, (description, defaults) in CAPABILITIES.items():
        cap, created = Capability.objects.get_or_create(code=code, defaults={"description": description})
        if created:
            for key in defaults:
                if key in roles:
                    roles[key].capabilities.add(cap)
    if SUPER_ADMIN in roles:
        roles[SUPER_ADMIN].capabilities.set(Capability.objects.all())


class Migration(migrations.Migration):
    dependencies = [("accounts", "0007_drop_legacy_role")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
