"""Objective 3: cookie JWT, rotation with blacklist, CSRF double-submit, sign in by username or email."""
import importlib
import json
import os
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from core.testing import PASSWORD

from .models import Department, User

LOGIN = "/api/v1/auth/login/"
REFRESH = "/api/v1/auth/refresh/"
LOGOUT = "/api/v1/auth/logout/"
ME = "/api/v1/auth/me/"


class CookieAuthCase(APITestCase):
    def setUp(self):
        self.admin = Department.objects.create(name="Administration")
        self.ceo = User.objects.create_user(email="Boss@X.com", password=PASSWORD, full_name="Boss", department=self.admin, role="head", username="TheBoss")

    def sign_in(self, identifier="boss@x.com", password=PASSWORD):
        return self.client.post(LOGIN, {"identifier": identifier, "password": password}, format="json")

    def csrf(self):
        return {"HTTP_X_CSRF_TOKEN": self.client.cookies["csrf_token"].value}


class LoginTests(CookieAuthCase):
    def test_email_or_username_any_case(self):
        for ident in ("boss@x.com", "BOSS@X.COM", "theboss", "THEBOSS", " TheBoss "):
            self.client.cookies.clear()
            self.assertEqual(self.sign_in(ident).status_code, 200, ident)

    def test_wrong_password_unknown_user_and_inactive_look_identical(self):
        wrong = self.sign_in(password="nope-nope-nope")
        unknown = self.sign_in("ghost")
        User.objects.filter(pk=self.ceo.pk).update(is_active=False)
        inactive = self.sign_in()
        self.assertEqual({wrong.status_code, unknown.status_code, inactive.status_code}, {401})
        self.assertEqual(wrong.data, unknown.data)
        self.assertEqual(wrong.data, inactive.data)

    def test_legacy_email_key_still_works(self):
        self.assertEqual(self.client.post(LOGIN, {"email": "boss@x.com", "password": PASSWORD}, format="json").status_code, 200)

    def test_username_is_unique_ignoring_case(self):
        hr = Department.objects.get(name="HR")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(email="o@x.com", password=PASSWORD, full_name="O", department=hr, username="theboss")


class TokensAreCookiesOnlyTests(CookieAuthCase):
    def test_tokens_are_never_in_the_body(self):
        res = self.sign_in()
        body = json.dumps(res.data)
        self.assertNotIn("access", res.data)
        self.assertNotIn("refresh", res.data)
        for cookie in ("access_token", "refresh_token"):
            self.assertNotIn(res.cookies[cookie].value, body)
        self.assertEqual(sorted(res.data), ["user"])

    def test_token_cookies_are_httponly_samesite_lax_and_scoped(self):
        res = self.sign_in()
        for name in ("access_token", "refresh_token"):
            c = res.cookies[name]
            self.assertTrue(c["httponly"], name)
            self.assertEqual(c["samesite"], "Lax", name)
        self.assertEqual(res.cookies["refresh_token"]["path"], "/api/v1/auth/")
        self.assertFalse(res.cookies["csrf_token"]["httponly"])  # the page must be able to read this one

    @override_settings(AUTH_COOKIE_SECURE=True)
    def test_secure_flag_follows_the_setting(self):
        res = self.sign_in()
        for name in ("access_token", "refresh_token", "csrf_token"):
            self.assertTrue(res.cookies[name]["secure"], name)

    def test_production_settings_force_secure_cookies(self):
        env = {"DJANGO_SECRET_KEY": "k" * 60, "DJANGO_ALLOWED_HOSTS": "app.example.com", "CORS_ALLOWED_ORIGINS": "https://app.example.com"}
        with mock.patch.dict(os.environ, env):
            import config.settings.production as prod

            self.assertTrue(importlib.reload(prod).AUTH_COOKIE_SECURE)
        os.environ.pop("DJANGO_ENV", None)

    def test_a_bearer_header_is_not_accepted(self):
        res = self.sign_in()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.cookies['access_token'].value}")
        self.assertEqual(client.get(ME).status_code, 401)

    def test_me_returns_the_user_and_capabilities(self):
        self.sign_in()
        res = self.client.get(ME)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["email"], "boss@x.com")
        self.assertIn("user.manage", res.data["capabilities"])
        self.assertNotIn("password", res.data)


class RefreshTests(CookieAuthCase):
    def test_refresh_rotates_and_the_old_token_is_rejected(self):
        self.sign_in()
        old = self.client.cookies["refresh_token"].value
        res = self.client.post(REFRESH, **self.csrf())
        self.assertEqual(res.status_code, 200)
        new = self.client.cookies["refresh_token"].value
        self.assertNotEqual(old, new)
        # Replay the first token from another client: refused.
        thief = APIClient()
        thief.cookies["refresh_token"] = old
        thief.cookies["csrf_token"] = "x" * 20
        replay = thief.post(REFRESH, HTTP_X_CSRF_TOKEN="x" * 20)
        self.assertEqual(replay.status_code, 401)
        # The new one still works.
        self.assertEqual(self.client.post(REFRESH, **self.csrf()).status_code, 200)

    def test_refresh_without_cookie_is_401(self):
        self.client.cookies["csrf_token"] = "abc"
        self.assertEqual(self.client.post(REFRESH, HTTP_X_CSRF_TOKEN="abc").status_code, 401)

    def test_refresh_needs_csrf(self):
        self.sign_in()
        self.assertEqual(self.client.post(REFRESH).status_code, 403)

    def test_new_access_token_works(self):
        self.sign_in()
        self.client.post(REFRESH, **self.csrf())
        self.assertEqual(self.client.get(ME).status_code, 200)


class LogoutTests(CookieAuthCase):
    def test_logout_clears_cookies_and_blacklists_the_refresh_token(self):
        self.sign_in()
        refresh = self.client.cookies["refresh_token"].value
        res = self.client.post(LOGOUT, **self.csrf())
        self.assertEqual(res.status_code, 204)
        for name in ("access_token", "refresh_token", "csrf_token"):
            self.assertEqual(res.cookies[name].value, "")
        again = APIClient()
        again.cookies["refresh_token"] = refresh
        again.cookies["csrf_token"] = "y" * 20
        self.assertEqual(again.post(REFRESH, HTTP_X_CSRF_TOKEN="y" * 20).status_code, 401)

    def test_logout_without_session_is_fine(self):
        self.assertEqual(APIClient().post(LOGOUT).status_code, 204)


class CsrfTests(CookieAuthCase):
    def test_unsafe_request_without_the_header_is_rejected(self):
        self.sign_in()
        res = self.client.patch(ME, {"preferred_language": "ar"}, format="json")
        self.assertEqual(res.status_code, 403)
        self.ceo.refresh_from_db()
        self.assertEqual(self.ceo.preferred_language, "en")

    def test_a_wrong_header_is_rejected_and_the_right_one_accepted(self):
        self.sign_in()
        self.assertEqual(self.client.patch(ME, {"preferred_language": "ar"}, format="json", HTTP_X_CSRF_TOKEN="wrong").status_code, 403)
        self.assertEqual(self.client.patch(ME, {"preferred_language": "ar"}, format="json", **self.csrf()).status_code, 200)

    def test_safe_requests_need_no_header(self):
        self.sign_in()
        self.assertEqual(self.client.get(ME).status_code, 200)

    def test_header_without_the_matching_cookie_is_rejected(self):
        self.sign_in()
        del self.client.cookies["csrf_token"]
        self.assertEqual(self.client.patch(ME, {"preferred_language": "ar"}, format="json", HTTP_X_CSRF_TOKEN="anything").status_code, 403)

    def test_anonymous_gets_401_not_403(self):
        self.assertEqual(APIClient().get(ME).status_code, 401)
