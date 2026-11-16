"""Objective 23: every permission rule has a denial test.

Two kinds of capability exist. One is named by an endpoint (`required_capabilities`): `FailClosedTests.test_removing_any_one_capability_closes_every_endpoint_that_names_it`
removes it from an otherwise all-powerful role and demands a 403 from every endpoint that names it, so it is tested by construction.
The other is consulted inside a rule (who may see this record, who may act at this step). Those have no endpoint to sweep, so this file makes
the gap impossible to grow: every capability in the catalogue must be either named by an endpoint or named in at least one test file, and
every test file that names a rule-level capability must also assert a refusal (403, 404 or a validation error) somewhere in it.

Honest limit: 27 rule-level capabilities are pinned below as KNOWN_GAPS. They are exercised only through role-based feature tests (for example a
Commercial member seeing only their own leads), not by a test that removes that one capability and shows the refusal. The list can only shrink:
adding a test that names one makes the equality below fail until the name is removed from the list, and a new capability cannot join it.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

from accounts.catalog import CAPABILITIES
from core import permission_audit
from core.tests_capabilities import needs

BACKEND = Path(__file__).resolve().parent.parent
REFUSAL = re.compile(r"(status_code, 40[0134]|assertEqual\([^)]*, 40[0134]\)|assertRaises|assertFalse\(.*(can_|has_capability)|PermissionDenied|ImmutableError)")


KNOWN_GAPS = {
    "lead.view_all", "lead.view_assigned", "lead.view_created", "lead.work_assigned", "lead.batches_all", "lead.edit_created", "appointment.view_all",
    "quotation.view_all", "quotation.view_assigned", "contract.view_all", "contract.view_assigned", "meeting_report.view_all", "operation.work",
    "operation.review", "operation.view_all_clients", "operation.view_own_deals", "payment.manage", "report.funnel", "report.revenue", "report.forecast",
    "report.operations", "report.hr", "hr.staff", "hr.manage", "hr.leave_request", "hr.leave_decide_hr_head", "hr.payroll_approve",
}


def test_files():
    return [p for p in BACKEND.rglob("tests*.py") if ".venv" not in p.parts and p.name != "tests_denial_coverage.py"]


def named_by_endpoints():
    used = set()
    for url, _ in permission_audit.endpoints():
        for method in permission_audit.METHODS:
            needed, _ = needs(method, url)
            if isinstance(needed, list):
                used |= set(needed)
    return used


class DenialCoverageTests(SimpleTestCase):
    def test_the_list_of_capabilities_without_their_own_denial_test_can_only_shrink(self):
        bodies = {p: p.read_text(encoding="utf-8") for p in test_files() if p.name != "tests_capabilities.py"}
        swept = named_by_endpoints()
        gaps = {c for c in CAPABILITIES if c not in swept and not any(c in b for b in bodies.values())}
        self.assertEqual(sorted(gaps - KNOWN_GAPS), [], "a new capability has no denial coverage: give it an endpoint requirement or a test that names it")
        self.assertEqual(sorted(KNOWN_GAPS - gaps), [], "these now have a test: remove them from KNOWN_GAPS")

    def test_every_test_file_that_names_a_rule_level_capability_also_checks_a_refusal(self):
        swept = named_by_endpoints()
        rule_level = [c for c in CAPABILITIES if c not in swept]
        weak = []
        for p in test_files():
            body = p.read_text(encoding="utf-8")
            named = [c for c in rule_level if c in body]
            if named and not REFUSAL.search(body):
                weak.append(f"{p.relative_to(BACKEND)} names {named} but never asserts a refusal")
        self.assertEqual(weak, [], "\n".join(weak))

    def test_the_sweep_really_covers_most_of_the_catalogue(self):
        swept = named_by_endpoints()
        self.assertGreaterEqual(len(swept), 40, "the endpoint sweep names suspiciously few capabilities")
        self.assertTrue({"gtask.access", "operation.access", "settings.manage"} <= swept)
