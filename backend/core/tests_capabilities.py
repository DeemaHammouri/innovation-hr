"""Objective 4: capability-based access control.

Everything here is generated from the URL table and the views' own declarations, so a new endpoint cannot slip in unguarded:

* every API view declares the capabilities it needs (or is public on purpose);
* a role holding NO capability reaches only the endpoints declared open to any signed-in person;
* taking away any single capability closes every endpoint that names it (a denial test for every capability);
* granting a capability to a role opens the endpoint with data alone, no view change.
"""
from django.urls import Resolver404, resolve
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from accounts.catalog import CAPABILITIES
from accounts.models import Capability, Role, User
from accounts.permissions import required_capabilities
from core import permission_audit
from core.testing import PASSWORD, RoleCase

# Public on purpose: they authenticate nobody and expose nothing. Anything else must declare capabilities.
PUBLIC_VIEWS = {"LoginView", "RefreshView", "LogoutView", "HealthView"}
# Open DRF index pages: no capability can open them, they are closed to everyone.
INDEX_URLS = {"/api/v1/", "/api/v1/lookups/"}


def view_for(method, url):
    """(view instance with its action set, request) exactly as DRF would build them, or None for a URL that does not resolve."""
    try:
        match = resolve(url)
    except Resolver404:
        return None, None  # a sample URL that matches no route answers 404 to everyone
    cls = getattr(match.func, "cls", None) or match.func.view_class
    actions = getattr(match.func, "actions", None) or {}
    view = cls(**getattr(match.func, "initkwargs", {}))
    view.action = actions.get(method)
    view.kwargs = match.kwargs
    request = Request(getattr(APIRequestFactory(), method)(url))
    view.request = request
    return view, request


def needs(method, url):
    view, request = view_for(method, url)
    if view is None:
        return "no-handler", None
    if view.action is None and getattr(view, method, None) is None:
        return "no-handler", view
    return required_capabilities(view, request), view


class DeclarationTests(RoleCase):
    def test_every_endpoint_declares_its_capabilities_or_is_public(self):
        undeclared = []
        for url, _ in permission_audit.endpoints():
            if url in INDEX_URLS:
                continue
            for method in permission_audit.METHODS:
                needed, view = needs(method, url)
                if needed == "no-handler":
                    continue
                if type(view).__name__ in PUBLIC_VIEWS:
                    continue
                if needed is None:
                    undeclared.append(f"{method.upper()} {url} ({type(view).__name__}.{view.action})")
        self.assertEqual(undeclared, [], "\n".join(undeclared[:30]))

    def test_every_declared_capability_exists_in_the_catalogue(self):
        unknown = set()
        for url, _ in permission_audit.endpoints():
            for method in permission_audit.METHODS:
                needed, _ = needs(method, url)
                if isinstance(needed, list):
                    unknown |= {c for c in needed if c not in CAPABILITIES}
        self.assertEqual(unknown, set())

    def test_every_catalogue_capability_is_used_by_an_endpoint_or_a_rule(self):
        used = set()
        for url, _ in permission_audit.endpoints():
            for method in permission_audit.METHODS:
                needed, _ = needs(method, url)
                if isinstance(needed, list):
                    used |= set(needed)
        # Capabilities consulted by object-level rules instead of an endpoint (visibility, flags, who may act at a step).
        in_rules = {
            "lead.view_all", "lead.view_assigned", "lead.view_created", "lead.work_assigned", "lead.edit_created",
            "quotation.view_all", "quotation.view_assigned", "contract.view_all", "contract.view_assigned",
            "handover.view", "handover.write", "handover.decide", "project.view", "project.staff", "operation.review", "operation.monitor", "operation.work", "operation.manage", "operation.view_all_clients", "operation.view_own_deals",
            "payment.manage", "hr.staff", "hr.manage", "hr.leave_request", "hr.leave_decide_hr_head", "hr.payroll_approve",
            "contract.sign", "contract.draft", "quotation.prepare", "quotation.sign", "lead.manage", "report.funnel", "report.revenue",
            "appointment.view_all", "meeting_report.view_all", "report.forecast", "report.operations", "report.hr", "lead.create", "lead.import", "lead.batches_all",
            "gtask.assign_team", "gtask.assign_any",
        }
        self.assertEqual(sorted(set(CAPABILITIES) - used - in_rules), [], "unused capabilities: delete them or wire them in")


def custom_role(key, capability_codes):
    role = Role.objects.create(key=key, name_en=key, name_ar=key)
    role.capabilities.set(Capability.objects.filter(code__in=capability_codes))
    return role


def custom_user(role):
    return User.objects.create_user(email=f"{role.key}@x.com", password=PASSWORD, full_name=role.key, role_ref=role)


class FailClosedTests(RoleCase):
    def test_a_role_with_no_capability_only_reaches_open_endpoints(self):
        nobody = custom_user(custom_role("nobody", []))
        self.client.force_authenticate(nobody)
        leaks = []
        for url, _ in permission_audit.endpoints():
            for method in permission_audit.METHODS:
                needed, view = needs(method, url)
                if needed == "no-handler" or type(view).__name__ in PUBLIC_VIEWS:
                    continue
                code = permission_audit.call(self.client, method, url).status_code
                if needed == [] or code in (401, 403, 404, 405):
                    # [] means "any signed-in person" (self-service data). 404 is a missing record, still no access.
                    if needed != [] and code not in (403, 404, 405, 401):
                        leaks.append(f"{method.upper()} {url} -> {code}")
                else:
                    leaks.append(f"{method.upper()} {url} -> {code}")
        self.assertEqual(leaks, [], "\n".join(leaks[:30]))

    def test_removing_any_one_capability_closes_every_endpoint_that_names_it(self):
        everything = set(CAPABILITIES)
        users = {}
        failures, checked = [], 0
        for url, _ in permission_audit.endpoints():
            for method in permission_audit.METHODS:
                needed, view = needs(method, url)
                if not isinstance(needed, list) or not needed:
                    continue
                for dropped in needed:
                    if dropped not in users:
                        users[dropped] = custom_user(custom_role("all_but_" + dropped.replace(".", "_"), everything - {dropped}))
                    self.client.force_authenticate(users[dropped])
                    code = permission_audit.call(self.client, method, url).status_code
                    checked += 1
                    if code != 403:
                        failures.append(f"{method.upper()} {url} without {dropped} -> {code}")
        self.assertGreater(checked, 100, "the generated denial test found suspiciously few cases")
        self.assertEqual(failures, [], "\n".join(failures[:30]))

    def test_inactive_users_hold_no_capability(self):
        ceo = self.users["ceo"]
        self.assertTrue(ceo.has_capability("user.manage"))
        User.objects.filter(pk=ceo.pk).update(is_active=False)
        ceo.refresh_from_db()
        self.assertFalse(ceo.has_capability("user.manage"))


class GrantTests(RoleCase):
    """A capability is data: grant it and the endpoint opens, with no change to any view."""

    URL = "/api/v1/payments/overview/"

    def test_granting_and_revoking_payment_view(self):
        member = self.as_role("hr_member")
        self.assertEqual(self.client.get(self.URL).status_code, 403)
        role = Role.objects.get(key="hr_member")
        role.capabilities.add(Capability.objects.get(code="payment.view"))
        member.refresh_from_db()
        self.assertEqual(self.client.get(self.URL).status_code, 200)
        role.capabilities.remove(Capability.objects.get(code="payment.view"))
        member.refresh_from_db()
        self.assertEqual(self.client.get(self.URL).status_code, 403)

    def test_super_admin_holds_everything(self):
        root = User.objects.create_superuser("root@x.com", PASSWORD, full_name="Root")
        self.client.force_authenticate(root)
        self.assertEqual(self.client.get(self.URL).status_code, 200)
        self.assertEqual(set(root.capability_codes), set(CAPABILITIES))
