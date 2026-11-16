"""Objectives 5 and 6: user management, first sign-in, password policy, revocation, lockout, audit trail, error envelope."""
import io
import json
import logging
from unittest import mock

from django.apps import apps
from django.contrib.auth.password_validation import CommonPasswordValidator
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from rest_framework.test import APIClient

from audit.events import SecretInAuditError, record_event
from audit.models import AuditEntry, SecurityEvent

from .models import ActionLog, User
from .tests import PASSWORD, BaseCase

STRONG = "Correct-Horse-Battery-9"


def fresh_client():
    c = APIClient()
    return c


def sign_in(client, email, password=PASSWORD, **extra):
    res = client.post("/api/v1/auth/login/", {"identifier": email, "password": password}, format="json", **extra)
    if res.status_code == 200:
        client.defaults["HTTP_X_CSRF_TOKEN"] = client.cookies["csrf_token"].value
    return res


class UserManagementTests(BaseCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.admin = fresh_client()
        sign_in(self.admin, "ceo@x.com")

    def payload(self, **over):
        data = {"full_name": "Sam Lee", "email": "sam@x.com", "department": self.dept["Commercial"].id, "role": "commercial_member"}
        data.update(over)
        return data

    def test_list_search_filter(self):
        self.make("hr@x.com", "HR")
        self.make("op@x.com", "Operation", "head")
        res = self.admin.get("/api/v1/users/?search=hr")
        self.assertEqual([u["email"] for u in res.data["results"]] if "results" in res.data else [u["email"] for u in res.data], ["hr@x.com"])
        rows = self.admin.get(f"/api/v1/users/?department={self.dept['Operation'].id}")
        self.assertEqual(len(rows.data["results"] if "results" in rows.data else rows.data), 1)
        self.admin.post(f"/api/v1/users/{User.objects.get(email='hr@x.com').id}/deactivate/")
        inactive = self.admin.get("/api/v1/users/?status=inactive")
        self.assertEqual(len(inactive.data["results"] if "results" in inactive.data else inactive.data), 1)

    def test_create_shows_a_16_character_password_once(self):
        res = self.admin.post("/api/v1/users/", self.payload(), format="json")
        self.assertEqual(res.status_code, 201, res.content)
        shown = res.data["temporary_password"]
        self.assertEqual(len(shown), 16)
        # Never again: not in the user, the list, nor the detail.
        uid = res.data["id"]
        for url in (f"/api/v1/users/{uid}/", "/api/v1/users/"):
            self.assertNotIn(shown, self.admin.get(url).content.decode())
        # Two people never get the same one.
        other = self.admin.post("/api/v1/users/", self.payload(email="b@x.com"), format="json").data["temporary_password"]
        self.assertNotEqual(shown, other)

    @override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.Argon2PasswordHasher"])
    def test_temporary_password_is_stored_only_as_an_argon2_hash(self):
        res = self.admin.post("/api/v1/users/", self.payload(), format="json")
        shown = res.data["temporary_password"]
        user = User.objects.get(email="sam@x.com")
        self.assertTrue(user.password.startswith("argon2$"))
        self.assertNotIn(shown, user.password)
        self.assertTrue(user.check_password(shown))

    def test_the_password_appears_nowhere_it_should_not(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        root = logging.getLogger()
        root.addHandler(handler)
        old = root.level
        root.setLevel(logging.DEBUG)
        try:
            shown = self.admin.post("/api/v1/users/", self.payload(), format="json").data["temporary_password"]
            uid = User.objects.get(email="sam@x.com").id
            reset = self.admin.post(f"/api/v1/users/{uid}/reset-password/").data["temporary_password"]
        finally:
            root.removeHandler(handler)
            root.setLevel(old)
        self.assertNotIn(shown, stream.getvalue())
        self.assertNotIn(reset, stream.getvalue())
        # Not in any column of any table (sessions, audit, action log, users...).
        hits = []
        with connection.cursor() as cur:
            for model in apps.get_models():
                for secret in (shown, reset):
                    for row in model.objects.all().values():
                        if any(secret in str(v) for v in row.values()):
                            hits.append((model.__name__, secret))
        self.assertEqual(hits, [])

    def test_first_sign_in_allows_only_me_password_change_and_sign_out(self):
        shown = self.admin.post("/api/v1/users/", self.payload(), format="json").data["temporary_password"]
        newbie = fresh_client()
        self.assertEqual(sign_in(newbie, "sam@x.com", shown).status_code, 200)
        self.assertTrue(newbie.get("/api/v1/auth/me/").data["must_change_password"])
        for url in ("/api/v1/my-work/", "/api/v1/leads/", "/api/v1/notifications/", "/api/v1/hr/leave/", "/api/v1/dashboard/summary/"):
            self.assertEqual(newbie.get(url).status_code, 403, url)
        self.assertEqual(newbie.post("/api/v1/auth/logout/").status_code, 204)
        # Sign in again and change it: everything opens.
        sign_in(newbie, "sam@x.com", shown)
        res = newbie.post("/api/v1/auth/change-password/", {"new_password": STRONG, "confirm_password": STRONG}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        newbie.defaults["HTTP_X_CSRF_TOKEN"] = newbie.cookies["csrf_token"].value
        self.assertEqual(newbie.get("/api/v1/my-work/").status_code, 200)

    def test_password_policy(self):
        shown = self.admin.post("/api/v1/users/", self.payload(full_name="Layla Hassan", email="layla.hassan@x.com"), format="json").data["temporary_password"]
        c = fresh_client()
        sign_in(c, "layla.hassan@x.com", shown)

        def attempt(pw):
            return c.post("/api/v1/auth/change-password/", {"new_password": pw, "confirm_password": pw}, format="json")

        common = sorted(p for p in CommonPasswordValidator().passwords if len(p) >= 12)[0]
        self.assertEqual(attempt("Short-1!a").status_code, 400)  # under 12
        self.assertEqual(attempt(common).status_code, 400)  # on the common list
        self.assertEqual(attempt("layla.hassan2026").status_code, 400)  # too like the person's own details
        self.assertEqual(attempt(shown).status_code, 400)  # the current (temporary) one
        self.assertEqual(attempt(STRONG).status_code, 200)
        # A later change also may not reuse the current password.
        c.defaults["HTTP_X_CSRF_TOKEN"] = c.cookies["csrf_token"].value
        again = c.post("/api/v1/auth/change-password/", {"current_password": STRONG, "new_password": STRONG, "confirm_password": STRONG}, format="json")
        self.assertEqual(again.status_code, 400)

    def test_super_admin_is_invisible_and_untouchable_for_the_ceo(self):
        root = User.objects.create_superuser("root@x.com", PASSWORD, full_name="Root")
        listing = self.admin.get("/api/v1/users/")
        self.assertNotIn("root@x.com", json.dumps(listing.data, default=str))
        for method, url in (("get", f"/api/v1/users/{root.id}/"), ("patch", f"/api/v1/users/{root.id}/"), ("post", f"/api/v1/users/{root.id}/deactivate/"), ("post", f"/api/v1/users/{root.id}/reset-password/")):
            self.assertEqual(getattr(self.admin, method)(url, {"full_name": "Hacked"}, format="json").status_code, 404, url)
        root.refresh_from_db()
        self.assertEqual(root.full_name, "Root")
        self.assertTrue(root.is_active)
        # And the role cannot be handed out: not offered, and refused when forged.
        keys = [r["key"] for r in self.admin.get("/api/v1/roles/").data]
        self.assertNotIn("super_admin", keys)
        forged = self.admin.post("/api/v1/users/", self.payload(role="super_admin"), format="json")
        self.assertEqual(forged.status_code, 400)

    def test_nobody_changes_their_own_role_department_or_status(self):
        me = self.ceo
        self.assertEqual(self.admin.patch(f"/api/v1/users/{me.id}/", {"department": self.dept["HR"].id, "role": "hr_head"}, format="json").status_code, 400)
        self.assertEqual(self.admin.post(f"/api/v1/users/{me.id}/deactivate/").status_code, 400)
        self.assertEqual(self.admin.post(f"/api/v1/users/{me.id}/activate/").status_code, 400)
        self.assertEqual(self.admin.post(f"/api/v1/users/{me.id}/reset-password/").status_code, 400)

    def test_role_choices_depend_on_the_department(self):
        hr = self.dept["HR"].id
        keys = sorted(r["key"] for r in self.admin.get(f"/api/v1/roles/?department={hr}").data)
        self.assertEqual(keys, ["hr_head", "hr_member"])
        wrong = self.admin.post("/api/v1/users/", self.payload(department=hr, role="commercial_member"), format="json")
        self.assertEqual(wrong.status_code, 400)
        self.assertIn("role", wrong.data)
        right = self.admin.post("/api/v1/users/", self.payload(department=hr, role="hr_member"), format="json")
        self.assertEqual(right.status_code, 201, right.content)

    def test_only_user_managers_reach_these_endpoints(self):
        self.make("hr@x.com", "HR")
        c = fresh_client()
        sign_in(c, "hr@x.com")
        for method, url in (("get", "/api/v1/users/"), ("post", "/api/v1/users/"), ("get", "/api/v1/roles/"), ("get", "/api/v1/departments/")):
            self.assertEqual(getattr(c, method)(url).status_code, 403, url)


class RevocationTests(BaseCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.admin = fresh_client()
        sign_in(self.admin, "ceo@x.com")
        self.member = self.make("m@x.com", "HR")
        self.session = fresh_client()
        self.assertEqual(sign_in(self.session, "m@x.com").status_code, 200)
        self.assertEqual(self.session.get("/api/v1/auth/me/").status_code, 200)

    def alive(self):
        return self.session.get("/api/v1/auth/me/").status_code == 200

    def test_password_change_revokes_other_sessions(self):
        other_device = fresh_client()
        sign_in(other_device, "m@x.com")
        res = self.session.post("/api/v1/auth/change-password/", {"current_password": PASSWORD, "new_password": STRONG, "confirm_password": STRONG}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(other_device.get("/api/v1/auth/me/").status_code, 401)  # the old token is void
        self.assertTrue(self.alive())  # this device was given a fresh one

    def test_reset_deactivation_and_role_change_void_the_old_token(self):
        self.assertTrue(self.alive())
        self.admin.post(f"/api/v1/users/{self.member.id}/reset-password/")
        self.assertFalse(self.alive())
        self.member.refresh_from_db()
        sign_in(self.session, "m@x.com", "wrong")  # still locked into the temporary password flow

    def test_role_change_voids_the_old_token(self):
        res = self.admin.patch(f"/api/v1/users/{self.member.id}/", {"role": "hr_head"}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertFalse(self.alive())

    def test_deactivation_voids_the_old_token(self):
        self.admin.post(f"/api/v1/users/{self.member.id}/deactivate/")
        self.assertFalse(self.alive())

    def test_refresh_token_is_void_too(self):
        self.admin.post(f"/api/v1/users/{self.member.id}/reset-password/")
        self.session.defaults["HTTP_X_CSRF_TOKEN"] = self.session.cookies["csrf_token"].value
        self.assertEqual(self.session.post("/api/v1/auth/refresh/").status_code, 401)


class LockoutTests(BaseCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def test_the_sixth_attempt_is_blocked_even_with_the_right_password(self):
        c = fresh_client()
        for _ in range(5):
            self.assertEqual(sign_in(c, "ceo@x.com", "wrong-wrong").status_code, 401)
        res = sign_in(c, "ceo@x.com", PASSWORD)
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.json()["error"]["code"], "rate_limited")

    def test_per_address_throttle(self):
        c = fresh_client()
        with override_settings(LOGIN_MAX_FAILS_PER_IP=3):
            for i in range(3):
                sign_in(c, f"ghost{i}@x.com", "x", REMOTE_ADDR="7.7.7.7")
            self.assertEqual(sign_in(c, "ceo@x.com", PASSWORD, REMOTE_ADDR="7.7.7.7").status_code, 429)
            self.assertEqual(sign_in(c, "ceo@x.com", PASSWORD, REMOTE_ADDR="7.7.7.8").status_code, 200)


class AuditTrailTests(BaseCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def test_sign_in_failure_password_user_and_language_events(self):
        admin = fresh_client()
        sign_in(admin, "ceo@x.com", "wrong-wrong", HTTP_USER_AGENT="TestBrowser/1.0")
        sign_in(admin, "ceo@x.com", PASSWORD, HTTP_USER_AGENT="TestBrowser/1.0")
        created = admin.post("/api/v1/users/", {"full_name": "Sam", "email": "sam@x.com", "department": self.dept["HR"].id, "role": "hr_member"}, format="json")
        uid = created.data["id"]
        admin.patch(f"/api/v1/users/{uid}/", {"role": "hr_head"}, format="json")
        admin.post(f"/api/v1/users/{uid}/reset-password/")
        admin.post(f"/api/v1/users/{uid}/deactivate/")
        admin.patch("/api/v1/auth/me/", {"preferred_language": "ar"}, format="json")
        events = {e.event for e in SecurityEvent.objects.all()}
        self.assertTrue({"login_failed", "login_success", "user_created", "user_updated", "password_reset", "user_deactivated", "language_changed"} <= events, events)
        ok = SecurityEvent.objects.get(event="login_success")
        self.assertEqual((ok.actor_id, ok.target_id, ok.user_agent), (self.ceo.id, self.ceo.id, "TestBrowser/1.0"))
        self.assertTrue(ok.ip_address)
        failed = SecurityEvent.objects.get(event="login_failed")
        self.assertEqual(failed.identifier, "ceo@x.com")
        self.assertEqual(SecurityEvent.objects.get(event="user_created").target_id, uid)
        self.assertEqual(SecurityEvent.objects.get(event="user_created").actor_id, self.ceo.id)
        lang = SecurityEvent.objects.get(event="language_changed")
        self.assertEqual(lang.detail, {"previous": "en", "chosen": "ar"})

    def test_password_change_is_recorded(self):
        c = fresh_client()
        sign_in(c, "ceo@x.com")
        c.post("/api/v1/auth/change-password/", {"current_password": PASSWORD, "new_password": STRONG, "confirm_password": STRONG}, format="json")
        self.assertTrue(SecurityEvent.objects.filter(event="password_changed", target=self.ceo).exists())

    def test_secret_like_fields_are_refused(self):
        request = mock.Mock(META={}, user=self.ceo)
        for bad in ({"password": "x"}, {"new_token": "y"}, {"authorization": "Bearer z"}, {"note": "aaaaaaaa.bbbbbbbb.cccccccc"}, {"extra": {"csrf": "1"}}):
            with self.assertRaises(SecretInAuditError, msg=bad):
                record_event(request, "x", **bad)
        self.assertFalse(SecurityEvent.objects.filter(event="x").exists())

    def test_the_trail_cannot_be_edited_or_deleted(self):
        c = fresh_client()
        sign_in(c, "ceo@x.com")
        event = SecurityEvent.objects.first()
        from audit.models import ImmutableError

        with self.assertRaises(ImmutableError):
            event.delete()
        with self.assertRaises(ImmutableError):
            SecurityEvent.objects.all().update(event="x")
        self.assertGreaterEqual(ActionLog.objects.count(), 1)
        self.assertEqual(AuditEntry.objects.filter(action="password").count(), 0)


class ErrorEnvelopeTests(BaseCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.c = fresh_client()
        sign_in(self.c, "ceo@x.com")

    def assert_shape(self, res, status, code=None):
        self.assertEqual(res.status_code, status, res.content)
        body = res.json()
        self.assertEqual(set(body), {"error"}, body)
        self.assertTrue({"code", "message"} <= set(body["error"]) <= {"code", "message", "fields"}, body)
        self.assertTrue(body["error"]["message"])
        if code:
            self.assertEqual(body["error"]["code"], code)
        self.assertNotIn("Traceback", res.content.decode())
        return body["error"]

    def test_401(self):
        self.assert_shape(fresh_client().get("/api/v1/auth/me/"), 401, "not_authenticated")

    def test_403(self):
        self.make("hr@x.com", "HR")
        c = fresh_client()
        sign_in(c, "hr@x.com")
        self.assert_shape(c.get("/api/v1/users/"), 403, "permission_denied")

    def test_404_record_and_unknown_route(self):
        self.assert_shape(self.c.get("/api/v1/users/99999/"), 404, "not_found")
        self.assert_shape(self.c.get("/api/v1/does-not-exist/"), 404, "not_found")

    def test_405(self):
        self.assert_shape(self.c.delete("/api/v1/auth/me/"), 405, "method_not_allowed")

    def test_429(self):
        c = fresh_client()
        for _ in range(5):
            sign_in(c, "ceo@x.com", "wrong-wrong")
        self.assert_shape(sign_in(c, "ceo@x.com", PASSWORD), 429, "rate_limited")

    def test_validation_errors_carry_fields(self):
        err = self.assert_shape(self.c.post("/api/v1/users/", {"full_name": "", "email": "nope"}, format="json"), 400, "validation_error")
        self.assertIn("fields", err)
        self.assertIn("email", err["fields"])

    def test_500_has_no_stack_trace_or_internals(self):
        quiet = APIClient(raise_request_exception=False)
        sign_in(quiet, "ceo@x.com")
        with mock.patch("accounts.views.MeView.get", side_effect=RuntimeError("secret-internal-detail /srv/app/models.py")):
            res = quiet.get("/api/v1/auth/me/")
        err = self.assert_shape(res, 500, "server_error")
        self.assertNotIn("secret-internal-detail", res.content.decode())
        self.assertNotIn(".py", res.content.decode())
        self.assertNotIn("fields", err)

    def test_every_error_status_across_the_api_uses_the_envelope(self):
        for method, url in (("get", "/api/v1/leads/99999/"), ("post", "/api/v1/leads/"), ("get", "/api/v1/reports/nope/"), ("patch", "/api/v1/auth/me/")):
            res = getattr(self.c, method)(url, {"preferred_language": "xx"} if method == "patch" else {}, format="json")
            if res.status_code >= 400:
                self.assert_shape(res, res.status_code)
