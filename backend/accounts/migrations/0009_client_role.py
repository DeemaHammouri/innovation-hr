"""The Client role and its single capability (portal.access), for installs that already have an organisation.

Same rule as 0008: only things that do not exist yet are created, nothing an administrator changed is touched. Safe on a fresh
database (nothing happens until roles exist) and reversible (a role in use is kept, so reversing does nothing)."""
from django.db import migrations

from accounts.catalog import CAPABILITIES, CLIENT, ROLES, SUPER_ADMIN


def forwards(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Capability = apps.get_model("accounts", "Capability")
    if not Role.objects.exists():
        return
    _, _, name_en, name_ar = ROLES[CLIENT][0], ROLES[CLIENT][1], ROLES[CLIENT][2], ROLES[CLIENT][3]
    role, _ = Role.objects.get_or_create(key=CLIENT, defaults={"is_head": False, "name_en": name_en, "name_ar": name_ar})
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
    dependencies = [("accounts", "0008_sync_new_capabilities")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
