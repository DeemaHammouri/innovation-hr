"""Phase 4: handover and project capabilities, and Operation stops seeing contracts.

Operation used to read a contract once it was handed over. It now receives a handover (what to deliver, who to talk to) and never the
contract, its prices or its file, so `contract.access` and `contract.view_handed_over` are taken away from the two Operation roles.
Reversible: going back gives those two capabilities to the Operation roles again."""
from django.db import migrations

from accounts.catalog import CAPABILITIES, SUPER_ADMIN

REVOKED = ["contract.access", "contract.view_handed_over"]
OPERATION_ROLES = ["operation_head", "operation_member"]


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
    for key in OPERATION_ROLES:
        if key in roles:
            roles[key].capabilities.remove(*Capability.objects.filter(code__in=REVOKED))
    if SUPER_ADMIN in roles:
        roles[SUPER_ADMIN].capabilities.set(Capability.objects.all())


def backwards(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Capability = apps.get_model("accounts", "Capability")
    for key in OPERATION_ROLES:
        role = Role.objects.filter(key=key).first()
        if role:
            role.capabilities.add(*Capability.objects.filter(code__in=REVOKED))


class Migration(migrations.Migration):
    dependencies = [("accounts", "0011_phase3_contract_capabilities")]
    operations = [migrations.RunPython(forwards, backwards)]
