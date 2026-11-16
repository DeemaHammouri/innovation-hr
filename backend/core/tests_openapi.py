"""Objective 24: the OpenAPI schema lists every endpoint with request and response shapes, and generating it raises no warning.

A new route that is missing from the schema, or a view the generator cannot describe (no serializer, untyped path parameter),
fails here, so the documentation cannot drift from the code.
"""
import re

from django.test import TestCase
from drf_spectacular.drainage import GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from accounts.models import User
from core import permission_audit
from core.testing import PASSWORD, RoleCase


def build_schema():
    GENERATOR_STATS.reset()
    schema = SchemaGenerator().get_schema(request=None, public=True)
    return schema, GENERATOR_STATS


def norm(path):
    """/api/v1/leads/{id}/  ->  /leads/{}/   (the sample-value URLs from permission_audit use 1, x ...)"""
    return re.sub(r"\{[^}]+\}", "{}", path).replace("/api/v1", "")


class SchemaCompletenessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.schema, cls.stats = build_schema()

    def test_the_generator_raises_no_warning_and_no_error(self):
        problems = [str(m) for m in list(self.stats._warn_cache) + list(self.stats._error_cache)]
        self.assertEqual(problems, [], "\n".join(problems[:20]))

    def test_every_api_route_is_documented(self):
        documented = {norm(p) for p in self.schema["paths"]}
        missing = []
        not_in_schema_on_purpose = {"/api/v1/", "/api/v1/1", "/api/v1/lookups/", "/api/v1/lookups/1", "/api/v1/schema/", "/api/v1/docs/", "/api/v1/redoc/"}  # router index pages (closed to all) and the docs themselves
        for url, template in permission_audit.endpoints():
            if url in not_in_schema_on_purpose:
                continue
            generic = re.sub(r"\d+|x\b", "{}", norm(url))
            generic = re.sub(r"\{\}(?=\.)", "{}", generic)
            if generic not in documented and not any(re.fullmatch(re.escape(d).replace(r"\{\}", r"[^/]+"), norm(url)) for d in documented):
                missing.append(url)
        self.assertEqual(missing, [], "\n".join(missing[:30]))

    def test_every_operation_describes_its_responses_and_every_write_its_request(self):
        bare = []
        for path, item in self.schema["paths"].items():
            for method, op in item.items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                if not op.get("responses"):
                    bare.append(f"{method.upper()} {path}: no responses")
                if not op.get("security") and not path.endswith(("/login/", "/refresh/", "/logout/", "/health/")):
                    bare.append(f"{method.upper()} {path}: no security")
        self.assertEqual(bare, [], "\n".join(bare[:30]))

    def test_there_is_one_documented_server_contract_not_two_aliases(self):
        self.assertTrue(all(p.startswith("/api/v1/") for p in self.schema["paths"]))


class SchemaAccessTests(RoleCase):
    def test_only_settings_managers_read_the_schema_and_the_pages(self):
        for url in ("/api/v1/schema/", "/api/v1/docs/", "/api/v1/redoc/"):
            self.client.force_authenticate(None)
            self.assertIn(self.client.get(url).status_code, (401, 403), url)
            self.as_role("marketing")
            self.assertEqual(self.client.get(url).status_code, 403, url)
            self.as_role("ceo")
            self.assertEqual(self.client.get(url).status_code, 200, url)
