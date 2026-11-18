"""P7 (full access): the Super Admin holds every capability that exists, including ones added after it was set up, with nothing granted."""
from django.test import TestCase

from accounts.models import Capability, Role, User
from accounts.organization import ensure_organization


class SuperAdminFullAccessTests(TestCase):
    def setUp(self):
        ensure_organization()
        self.admin = User.objects.create_superuser(email="root@x.com", password="x", full_name="Root")
        self.ceo = User.objects.create_user(email="ceo@x.com", password="x", full_name="Ceo", department=Role.objects.get(key="ceo").department, role="head")

    def test_the_super_admin_role_is_flagged_and_no_other_role_is(self):
        self.assertEqual(list(Role.objects.filter(full_access=True).values_list("key", flat=True)), ["super_admin"])

    def test_a_capability_created_later_reaches_the_super_admin_without_a_seed_or_a_grant(self):
        cap = Capability.objects.create(code="brand.new_thing")  # no ensure_organization, no migration, no role.capabilities.add
        self.assertFalse(Role.objects.get(key="super_admin").capabilities.filter(pk=cap.pk).exists())
        fresh = User.objects.get(pk=self.admin.pk)
        self.assertTrue(fresh.has_capability("brand.new_thing"))
        self.assertIn("brand.new_thing", fresh.capability_codes)

    def test_other_roles_do_not_get_a_new_capability(self):
        Capability.objects.create(code="brand.new_thing")
        self.assertFalse(User.objects.get(pk=self.ceo.pk).has_capability("brand.new_thing"))

    def test_the_super_admin_holds_every_existing_capability(self):
        self.assertEqual(User.objects.get(pk=self.admin.pk).capability_codes, frozenset(Capability.objects.values_list("code", flat=True)))

    def test_an_inactive_super_admin_holds_nothing(self):
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        self.assertEqual(User.objects.get(pk=self.admin.pk).capability_codes, frozenset())

    def test_looking_up_capabilities_stays_one_query(self):
        user = User.objects.get(pk=self.admin.pk)
        with self.assertNumQueries(1):
            user.capability_codes  # noqa: B018
