"""Give every existing user a Role from their department and head/member flag. Reversible: going back rewrites the old column."""
from django.db import migrations

from accounts.catalog import CAPABILITIES, DEPARTMENT_NAMES, ROLES, SUPER_ADMIN


def forwards(apps, schema_editor):
    Department = apps.get_model("accounts", "Department")
    Role = apps.get_model("accounts", "Role")
    Capability = apps.get_model("accounts", "Capability")
    User = apps.get_model("accounts", "User")
    if not User.objects.exists():
        return  # a fresh database: `seed_organization` (or the first user created) sets the organisation up
    depts = {name: Department.objects.get_or_create(name=name)[0] for name in DEPARTMENT_NAMES}
    roles = {}
    for key, (dept, is_head, name_en, name_ar) in ROLES.items():
        roles[key], _ = Role.objects.get_or_create(key=key, defaults={"department": depts.get(dept), "is_head": is_head, "name_en": name_en, "name_ar": name_ar})
    for code, (description, defaults) in CAPABILITIES.items():
        cap, created = Capability.objects.get_or_create(code=code, defaults={"description": description})
        if created:
            for key in defaults:
                roles[key].capabilities.add(cap)
    roles[SUPER_ADMIN].capabilities.set(Capability.objects.all())

    for user in User.objects.all():
        if user.department_id is None:
            role = roles[SUPER_ADMIN] if user.is_superuser else None
        else:
            name = user.department.name
            head = user.role == "head"
            role = next((r for r in roles.values() if r.department_id == user.department_id and (r.is_head == head or name == "Marketing")), None)
        user.role_ref = role
        user.is_dept_head = bool(role and role.is_head and user.department_id)
        user.save(update_fields=["role_ref", "is_dept_head"])


def backwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.all():
        user.role = "head" if user.role_ref_id and user.role_ref.is_head and user.department_id else "member"
        user.save(update_fields=["role"])
    User.objects.update(role_ref=None, is_dept_head=False)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_organization")]
    operations = [migrations.RunPython(forwards, backwards)]
