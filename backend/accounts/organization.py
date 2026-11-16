"""Create (or complete) the departments, roles and capabilities. Safe to run any number of times.

Existing rows are never reset: a capability an administrator granted or removed stays as it is. Only capabilities that did not exist
yet are attached to their default roles, and Super Admin always gets all of them.
"""
from django.db import transaction

from .catalog import CAPABILITIES, DEPARTMENT_NAMES, ROLES, SUPER_ADMIN
from .models import Capability, Department, Role


@transaction.atomic
def ensure_organization():
    depts = {name: Department.objects.get_or_create(name=name)[0] for name in DEPARTMENT_NAMES}
    roles = {}
    for key, (dept, is_head, name_en, name_ar) in ROLES.items():
        role, _ = Role.objects.get_or_create(
            key=key, defaults={"department": depts.get(dept), "is_head": is_head, "name_en": name_en, "name_ar": name_ar},
        )
        roles[key] = role
    new = []
    for code, (description, defaults) in CAPABILITIES.items():
        cap, created = Capability.objects.get_or_create(code=code, defaults={"description": description})
        if created:
            new.append(cap)
            for role_key in defaults:
                roles[role_key].capabilities.add(cap)
    roles[SUPER_ADMIN].capabilities.set(Capability.objects.all())
    return roles
