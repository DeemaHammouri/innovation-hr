import importlib
import logging
import os
from unittest import mock

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from accounts.models import Department, User
from core import permission_audit
from core.logscrub import ScrubFilter, scrub
from core.roles import ALL_ROLES
from core.testing import PASSWORD, RoleCase

LOGIN = "/api/auth/login/"


class PermissionAuditTests(RoleCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_sweep(self):
        table = permission_audit.matrix(self)
        self.assertGreater(len(table), 200, "the walker found suspiciously few endpoints")
        problems = []
        for (method, url), row in table.items():
            public = (method, url) in permission_audit.PUBLIC
            if not public and row["anon"] not in (401, 403, 404, 405):
                problems.append(f"anonymous {method.upper()} {url} -> {row['anon']}")
            for who, code in row.items():
                if code >= 500:
                    problems.append(f"{who} {method.upper()} {url} -> {code}")
        self.assertEqual(problems, [], "\n".join(problems[:40]))
        if os.environ.get("WRITE_PERMISSIONS"):
            self.write_doc(table)

    def test_public_list_is_exactly_the_sign_in_flow(self):
        for method, url in permission_audit.PUBLIC:
            self.client.force_authenticate(None)
            self.assertNotIn(permission_audit.call(self.client, method, url).status_code, (404, 405), f"{method} {url} no longer exists; update PUBLIC")

    def write_doc(self, table):
        short = {"anon": "anon", "ceo": "CEO", "marketing": "Mkt", "commercial_head": "ComH", "commercial_member": "ComM", "hr_head": "HRH", "hr_member": "HRM", "operation_head": "OpH", "operation_member": "OpM"}
        cols = ["anon"] + ALL_ROLES
        lines = ["| Method | Endpoint | " + " | ".join(short[c] for c in cols) + " |", "|---|---|" + "---|" * len(cols)]
        for (method, url), row in sorted(table.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            if all(row[c] in (404, 405) for c in ALL_ROLES):
                continue  # needs a real record to say anything, or the method does not exist
            lines.append(f"| {method.upper()} | `{url}` | " + " | ".join(str(row[c]) for c in cols) + " |")
        with open(os.environ["WRITE_PERMISSIONS"], "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


class LoginLockoutTests(RoleCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def bad(self, email="ceo@x.com", n=1):
        for _ in range(n):
            res = self.client.post(LOGIN, {"email": email, "password": "wrong"}, format="json")
        return res

    def test_locks_after_repeated_failures_even_with_the_right_password(self):
        self.assertEqual(self.bad(n=5).status_code, 401)
        res = self.client.post(LOGIN, {"email": "ceo@x.com", "password": PASSWORD}, format="json")
        self.assertEqual(res.status_code, 429)
        self.assertIn("Too many", res.data["detail"])

    def test_other_accounts_are_not_locked_by_one(self):
        self.bad(n=5)
        res = self.client.post(LOGIN, {"email": "marketing@x.com", "password": PASSWORD}, format="json")
        self.assertEqual(res.status_code, 200)

    def test_success_resets_the_counter(self):
        self.bad(n=4)
        self.assertEqual(self.client.post(LOGIN, {"email": "ceo@x.com", "password": PASSWORD}, format="json").status_code, 200)
        self.assertEqual(self.bad(n=4).status_code, 401)

    def test_ip_limit_and_forged_forwarded_header_ignored(self):
        with override_settings(LOGIN_MAX_FAILS_PER_IP=3, LOGIN_MAX_FAILS_PER_EMAIL=100):
            for i in range(3):
                self.client.post(LOGIN, {"email": f"nobody{i}@x.com", "password": "x"}, format="json", HTTP_X_FORWARDED_FOR=f"9.9.9.{i}")
            res = self.client.post(LOGIN, {"email": "ceo@x.com", "password": PASSWORD}, format="json", HTTP_X_FORWARDED_FOR="8.8.8.8")
            self.assertEqual(res.status_code, 429)  # rotating the header did not help the attacker

    def test_unknown_and_wrong_look_the_same(self):
        a = self.bad("ghost@x.com")
        b = self.bad("ceo@x.com")
        self.assertEqual((a.status_code, a.data), (b.status_code, b.data))


class HealthAndErrorTests(APITestCase):
    def test_health_is_public_and_minimal(self):
        res = self.client.get("/api/health/")
        self.assertEqual((res.status_code, res.data), (200, {"status": "ok"}))

    def test_health_reports_down_without_details(self):
        with mock.patch("django.db.backends.utils.CursorWrapper.execute", side_effect=Exception("secret db detail")):
            res = self.client.get("/api/health/")
        self.assertEqual(res.status_code, 503)
        self.assertNotIn("secret", str(res.data))

    def test_unknown_url_is_json(self):
        res = self.client.get("/api/nothing-here/")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res["Content-Type"], "application/json")


class ConstraintTests(RoleCase):
    def test_database_refuses_a_second_active_head(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.users["hr_member"].pk).update(is_dept_head=True)  # bypasses the model check on purpose

    def test_an_inactive_head_does_not_block_a_new_one(self):
        User.objects.filter(pk=self.users["hr_head"].pk).update(is_active=False)
        User.objects.filter(pk=self.users["hr_member"].pk).update(is_dept_head=True)

    def test_client_cadence_range(self):
        from clients.models import Client

        with self.assertRaises(IntegrityError), transaction.atomic():
            Client.objects.create(company_name="Bad", created_by=self.users["ceo"], qa_cadence_days=3)


class ScrubTests(SimpleTestCase):
    def test_masks_secrets(self):
        self.assertNotIn("hunter2", scrub("login failed password=hunter2 for x"))
        self.assertNotIn("abc.def.ghi", scrub("Authorization: Bearer abc.def.ghi"))
        self.assertNotIn("4321", scrub("{'base_salary': '4321.00'}"))
        self.assertIn("ordinary text", scrub("ordinary text"))

    def test_filter_masks_formatted_records(self):
        rec = logging.LogRecord("x", logging.ERROR, "f", 1, "bad token=%s", ("SECRET123",), None)
        ScrubFilter().filter(rec)
        self.assertNotIn("SECRET123", rec.getMessage())


class ProductionSettingsTests(SimpleTestCase):
    GOOD = {"DJANGO_SECRET_KEY": "k" * 60, "DJANGO_ALLOWED_HOSTS": "app.example.com", "CORS_ALLOWED_ORIGINS": "https://app.example.com"}

    def load(self, **env):
        with mock.patch.dict(os.environ, env, clear=False):
            import config.settings.production as prod

            return importlib.reload(prod)

    def tearDown(self):
        os.environ.pop("DJANGO_ENV", None)

    def test_good_configuration(self):
        s = self.load(**self.GOOD)
        self.assertFalse(s.DEBUG)
        self.assertTrue(s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE and s.SECURE_SSL_REDIRECT)
        self.assertEqual(s.ALLOWED_HOSTS, ["app.example.com"])
        self.assertEqual(s.REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"], ["rest_framework.renderers.JSONRenderer"])

    def test_refuses_weak_or_missing_values(self):
        for bad in (
            {**self.GOOD, "DJANGO_SECRET_KEY": "short"},
            {**self.GOOD, "DJANGO_SECRET_KEY": "dev-only-" + "x" * 60},
            {**self.GOOD, "DJANGO_ALLOWED_HOSTS": "*"},
            {**self.GOOD, "DJANGO_ALLOWED_HOSTS": ""},
            {**self.GOOD, "CORS_ALLOWED_ORIGINS": "http://app.example.com"},
            {**self.GOOD, "CORS_ALLOWED_ORIGINS": ""},
        ):
            with self.assertRaises(ImproperlyConfigured, msg=str(bad)):
                self.load(**bad)

    def test_missing_secret_refused(self):
        env = {k: v for k, v in os.environ.items() if k != "DJANGO_SECRET_KEY"}
        with mock.patch.dict(os.environ, env, clear=True), self.assertRaises(ImproperlyConfigured):
            import config.settings.production as prod

            importlib.reload(prod)
