"""Objective 2: departments, roles and capabilities as data."""
from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APITestCase

from core.testing import PASSWORD

from .catalog import CAPABILITIES, DEPARTMENT_NAMES, ROLES, SUPER_ADMIN
from .models import Capability, Department, Role, User


def snapshot():
    return (
        sorted(Department.objects.values_list("name", flat=True)),
        sorted(Role.objects.values_list("key", "is_head", "department__name")),
        sorted(Capability.objects.values_list("code", flat=True)),
        sorted((r.key, sorted(r.capabilities.values_list("code", flat=True))) for r in Role.objects.all()),
    )


class SeedOrganizationTests(TestCase):
    def test_creates_five_departments_ten_roles_and_every_capability(self):
        call_command("seed_organization", stdout=StringIO())
        self.assertEqual(Department.objects.count(), 5)
        self.assertEqual(sorted(Department.objects.values_list("name", flat=True)), sorted(DEPARTMENT_NAMES))
        self.assertEqual(Role.objects.count(), 10)
        self.assertEqual(Role.objects.filter(is_head=True).count(), 4)  # CEO + three department heads
        self.assertEqual(Capability.objects.count(), len(CAPABILITIES))

    def test_running_it_twice_changes_nothing(self):
        call_command("seed_organization", stdout=StringIO())
        first = snapshot()
        call_command("seed_organization", stdout=StringIO())
        self.assertEqual(snapshot(), first)

    def test_it_never_resets_grants_an_administrator_changed(self):
        call_command("seed_organization", stdout=StringIO())
        member = Role.objects.get(key="hr_member")
        member.capabilities.add(Capability.objects.get(code="payment.view"))
        member.capabilities.remove(Capability.objects.get(code="quotation.prepare"))
        before = snapshot()
        call_command("seed_organization", stdout=StringIO())
        self.assertEqual(snapshot(), before)

    def test_super_admin_holds_every_capability_including_new_ones(self):
        call_command("seed_organization", stdout=StringIO())
        admin = Role.objects.get(key=SUPER_ADMIN)
        self.assertEqual(admin.capabilities.count(), Capability.objects.count())
        self.assertIsNone(admin.department)
        Capability.objects.create(code="future.thing")  # created by hand, not in the catalogue
        call_command("seed_organization", stdout=StringIO())
        self.assertTrue(admin.capabilities.filter(code="future.thing").exists())

    def test_roles_belong_to_the_right_departments(self):
        call_command("seed_organization", stdout=StringIO())
        for key, (dept, is_head, *_names) in ROLES.items():
            role = Role.objects.get(key=key)
            self.assertEqual(role.department.name if role.department else None, dept)
            self.assertEqual(role.is_head, is_head)


class CapabilityGrantTests(APITestCase):
    """Capabilities come from the database. (The end-to-end "grant it and the endpoint opens" proof is in tests_capabilities.py.)"""

    def test_super_admin_has_every_capability_with_no_department(self):
        su = User.objects.create_superuser("root@x.com", PASSWORD, full_name="Root")
        self.assertEqual(su.role_name, SUPER_ADMIN)
        self.assertEqual(su.capability_codes, frozenset(CAPABILITIES))

    def test_an_inactive_user_holds_nothing(self):
        call_command("seed_organization", stdout=StringIO())
        ceo = User.objects.create_user(email="c@x.com", password=PASSWORD, full_name="C", department=Department.objects.get(name="Administration"), role="head")
        self.assertTrue(ceo.capability_codes)
        ceo.is_active = False
        ceo.save()
        self.assertEqual(ceo.capability_codes, frozenset())


class BackfillMigrationTests(TransactionTestCase):
    """The data migration gives existing users a role, and going back restores the old head/member column."""

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate([("accounts", target)])
        return executor.loader.project_state([("accounts", target)]).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())

    def test_forwards_and_backwards(self):
        old = self.migrate("0004_organization")  # the old column exists again here
        Dept, OldUser = old.get_model("accounts", "Department"), old.get_model("accounts", "User")
        hr, mk = Dept.objects.create(name="HR"), Dept.objects.create(name="Marketing")
        OldUser.objects.create(email="h@x.com", full_name="H", department=hr, role="head")
        OldUser.objects.create(email="m@x.com", full_name="M", department=hr, role="member")
        OldUser.objects.create(email="k@x.com", full_name="K", department=mk, role="member")
        OldUser.objects.create(email="dev@x.com", full_name="Dev", is_superuser=True)

        new = self.migrate("0006_head_constraint_username")
        U = new.get_model("accounts", "User")
        got = {u.email: (u.role_ref.key if u.role_ref_id else None, u.is_dept_head) for u in U.objects.all()}
        self.assertEqual(got, {"h@x.com": ("hr_head", True), "m@x.com": ("hr_member", False), "k@x.com": ("marketing", False), "dev@x.com": ("super_admin", False)})

        back = self.migrate("0004_organization")
        roles = {u.email: u.role for u in back.get_model("accounts", "User").objects.all()}
        self.assertEqual(roles["h@x.com"], "head")
        self.assertEqual(roles["m@x.com"], "member")
