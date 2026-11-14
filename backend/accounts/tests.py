from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase

from clients.models import Client

from .models import ActionLog, Department, DEPARTMENT_NAMES, User

PASSWORD = "temp-pass-123"


class BaseCase(APITestCase):
    def setUp(self):
        self.dept = {n: Department.objects.create(name=n) for n in DEPARTMENT_NAMES}
        self.ceo = self.make("ceo@x.com", "Administration", "head")

    def make(self, email, dept, role="member", **extra):
        return User.objects.create_user(
            email=email, password=PASSWORD, full_name=email.split("@")[0], department=self.dept[dept], role=role, **extra
        )

    def login(self, user, password=PASSWORD):
        res = self.client.post("/api/auth/login/", {"email": user.email, "password": password})
        self.assertEqual(res.status_code, 200, res.content)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        return res

    def new_user_payload(self, **over):
        data = {
            "full_name": "Sam Lee", "email": "sam@x.com", "department": self.dept["Commercial"].id,
            "role": "member", "temporary_password": "Temp-1234",
        }
        data.update(over)
        return data


class DepartmentRulesTests(BaseCase):
    def test_administration_only_has_the_ceo(self):
        with self.assertRaises(ValidationError):
            self.make("second@x.com", "Administration", "head")
        with self.assertRaises(ValidationError):
            self.make("member@x.com", "Administration", "member")

    def test_marketing_has_one_user(self):
        self.make("m1@x.com", "Marketing")
        with self.assertRaises(ValidationError):
            self.make("m2@x.com", "Marketing")

    def test_one_head_per_department_many_members(self):
        self.make("h1@x.com", "Operation", "head")
        with self.assertRaises(ValidationError):
            self.make("h2@x.com", "Operation", "head")
        self.make("a@x.com", "Operation")
        self.make("b@x.com", "Operation")

    def test_api_shows_clear_error_for_second_head(self):
        self.make("h1@x.com", "HR", "head")
        self.login(self.ceo)
        res = self.client.post("/api/users/", self.new_user_payload(department=self.dept["HR"].id, role="head"))
        self.assertEqual(res.status_code, 400)
        self.assertIn("already has a head", str(res.data["role"]))

    def test_changing_a_role_cannot_create_a_second_head(self):
        self.make("h1@x.com", "HR", "head")
        member = self.make("m@x.com", "HR")
        self.login(self.ceo)
        res = self.client.patch(f"/api/users/{member.id}/", {"role": "head"})
        self.assertEqual(res.status_code, 400)


class UserManagementTests(BaseCase):
    def test_only_ceo_can_manage_users(self):
        head = self.make("op@x.com", "Operation", "head")
        member = self.make("hr@x.com", "HR")
        for user in (head, member):
            self.login(user)
            self.assertEqual(self.client.get("/api/users/").status_code, 403)
            self.assertEqual(self.client.post("/api/users/", self.new_user_payload()).status_code, 403)
            self.assertEqual(self.client.post(f"/api/users/{self.ceo.id}/reset-password/").status_code, 403)

    def test_anonymous_gets_401(self):
        self.assertEqual(self.client.get("/api/users/").status_code, 401)

    def test_ceo_creates_user_with_forced_password_change(self):
        self.login(self.ceo)
        res = self.client.post("/api/users/", self.new_user_payload())
        self.assertEqual(res.status_code, 201, res.content)
        user = User.objects.get(email="sam@x.com")
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.check_password("Temp-1234"))

    def test_duplicate_email_and_short_password_are_rejected(self):
        self.login(self.ceo)
        self.client.post("/api/users/", self.new_user_payload())
        dup = self.client.post("/api/users/", self.new_user_payload(email="SAM@x.com"))
        self.assertEqual(dup.status_code, 400)
        short = self.client.post("/api/users/", self.new_user_payload(email="n@x.com", temporary_password="123"))
        self.assertEqual(short.status_code, 400)

    def test_deactivate_blocks_login_and_activate_restores_it(self):
        member = self.make("hr@x.com", "HR")
        self.login(self.ceo)
        self.assertEqual(self.client.post(f"/api/users/{member.id}/deactivate/").status_code, 200)
        self.client.credentials()
        res = self.client.post("/api/auth/login/", {"email": member.email, "password": PASSWORD})
        self.assertEqual(res.status_code, 401)
        self.login(self.ceo)
        self.client.post(f"/api/users/{member.id}/activate/")
        self.client.credentials()
        self.login(member)

    def test_ceo_cannot_deactivate_self(self):
        self.login(self.ceo)
        self.assertEqual(self.client.post(f"/api/users/{self.ceo.id}/deactivate/").status_code, 400)

    def test_reset_password_forces_change(self):
        member = self.make("hr@x.com", "HR")
        self.login(self.ceo)
        res = self.client.post(f"/api/users/{member.id}/reset-password/")
        self.assertEqual(res.status_code, 200)
        member.refresh_from_db()
        self.assertTrue(member.must_change_password)
        self.assertTrue(member.check_password(res.data["temporary_password"]))


class ForcedPasswordChangeTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.op = self.make("op@x.com", "Operation", "head", must_change_password=True)

    def test_other_endpoints_are_blocked_until_changed(self):
        self.login(self.op)
        for url in ("/api/clients/", "/api/users/", "/api/departments/"):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 403, url)
        self.assertEqual(self.client.post("/api/clients/", {"company_name": "Acme"}).status_code, 403)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)  # needed to know where to send the user

    def test_must_differ_from_temporary_and_confirm_must_match(self):
        self.login(self.op)
        same = self.client.post("/api/auth/change-password/", {"new_password": PASSWORD, "confirm_password": PASSWORD})
        self.assertEqual(same.status_code, 400)
        short = self.client.post("/api/auth/change-password/", {"new_password": "short", "confirm_password": "short"})
        self.assertEqual(short.status_code, 400)
        mismatch = self.client.post(
            "/api/auth/change-password/", {"new_password": "brand-new-1", "confirm_password": "brand-new-2"}
        )
        self.assertEqual(mismatch.status_code, 400)

    def test_change_unlocks_everything_and_old_password_stops_working(self):
        self.login(self.op)
        res = self.client.post(
            "/api/auth/change-password/", {"new_password": "brand-new-1", "confirm_password": "brand-new-1"}
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(self.client.get("/api/clients/").status_code, 200)
        self.client.credentials()
        self.assertEqual(
            self.client.post("/api/auth/login/", {"email": "op@x.com", "password": PASSWORD}).status_code, 401
        )

    def test_change_password_is_not_available_once_set(self):
        self.login(self.ceo)
        res = self.client.post(
            "/api/auth/change-password/", {"new_password": "brand-new-1", "confirm_password": "brand-new-1"}
        )
        self.assertEqual(res.status_code, 403)


class LoginLogTests(BaseCase):
    def test_login_and_logout_are_logged_with_ip(self):
        res = self.login(self.ceo)
        self.client.post("/api/auth/logout/", {"refresh": res.data["refresh"]})
        actions = list(ActionLog.objects.filter(user=self.ceo).order_by("id").values_list("action", flat=True))
        self.assertEqual(actions, ["login", "logout"])
        self.assertTrue(ActionLog.objects.first().ip_address)

    def test_failed_login_message_is_identical_for_unknown_email_and_wrong_password(self):
        wrong = self.client.post("/api/auth/login/", {"email": "ceo@x.com", "password": "nope-nope"})
        unknown = self.client.post("/api/auth/login/", {"email": "ghost@x.com", "password": "nope-nope"})
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(wrong.data, unknown.data)
        self.assertEqual(ActionLog.objects.count(), 0)


class ClientPermissionTests(BaseCase):
    def test_operation_head_and_ceo_can_create_and_edit(self):
        op = self.make("op@x.com", "Operation", "head")
        for user in (op, self.ceo):
            self.client.credentials()
            self.login(user)
            res = self.client.post("/api/clients/", {"company_name": f"Acme {user.id}"})
            self.assertEqual(res.status_code, 201, res.content)
            self.assertEqual(res.data["created_by"], user.id)
            patch = self.client.patch(f"/api/clients/{res.data['id']}/", {"phone": "123"})
            self.assertEqual(patch.status_code, 200)
        self.assertEqual(Client.objects.count(), 2)

    def test_everyone_else_is_refused(self):
        member = self.make("op2@x.com", "Operation", "member")
        hr_head = self.make("hr@x.com", "HR", "head")
        for user in (member, hr_head):
            self.client.credentials()
            self.login(user)
            self.assertEqual(self.client.get("/api/clients/").status_code, 403)
            self.assertEqual(self.client.post("/api/clients/", {"company_name": "Acme"}).status_code, 403)

    def test_company_name_is_required_and_search_works(self):
        self.login(self.ceo)
        self.assertEqual(self.client.post("/api/clients/", {"company_name": " "}).status_code, 400)
        self.client.post("/api/clients/", {"company_name": "Acme Ltd"})
        self.client.post("/api/clients/", {"company_name": "Globex"})
        res = self.client.get("/api/clients/?search=acme")
        self.assertEqual([c["company_name"] for c in res.data], ["Acme Ltd"])

    def test_no_delete(self):
        self.login(self.ceo)
        c = self.client.post("/api/clients/", {"company_name": "Acme"}).data
        self.assertEqual(self.client.delete(f"/api/clients/{c['id']}/").status_code, 405)


class PreferredLanguageTests(BaseCase):
    def test_defaults_to_english_and_user_can_change_only_that_field(self):
        self.login(self.ceo)
        self.assertEqual(self.client.get("/api/auth/me/").data["preferred_language"], "en")
        res = self.client.patch(
            "/api/auth/me/", {"preferred_language": "ar", "role": "member", "full_name": "Hacked"}, format="json"
        )
        self.assertEqual(res.status_code, 200)
        self.ceo.refresh_from_db()
        self.assertEqual(self.ceo.preferred_language, "ar")
        self.assertEqual(self.ceo.role, "head")
        self.assertEqual(self.ceo.full_name, "ceo")

    def test_invalid_language_is_rejected(self):
        self.login(self.ceo)
        self.assertEqual(self.client.patch("/api/auth/me/", {"preferred_language": "fr"}, format="json").status_code, 400)

    def test_ceo_can_set_language_when_creating_a_user(self):
        self.login(self.ceo)
        res = self.client.post("/api/users/", self.new_user_payload(preferred_language="ar"), format="json")
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.data["preferred_language"], "ar")

    def test_anonymous_cannot_patch(self):
        self.assertEqual(self.client.patch("/api/auth/me/", {"preferred_language": "ar"}, format="json").status_code, 401)


class DashboardSummaryTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.ops = self.make("ops@x.com", "Operation", "head")
        self.member = self.make("mem@x.com", "Commercial")
        self.pending = self.make("new@x.com", "HR", must_change_password=True)
        Client.objects.create(company_name="Acme", created_by=self.ops)
        Client.objects.create(company_name="Beta", created_by=self.ceo)

    def test_ceo_sees_people_and_client_numbers(self):
        self.login(self.ceo)
        res = self.client.get("/api/dashboard/summary/")
        self.assertEqual(res.status_code, 200)
        ceo = res.data["ceo"]
        self.assertEqual(ceo["total_users"], 4)
        self.assertEqual(ceo["active_users"], 4)
        self.assertEqual(ceo["pending_password_users"], 1)
        self.assertEqual(ceo["total_clients"], 2)
        counts = {d["department"]: d["count"] for d in ceo["users_by_department"]}
        self.assertEqual(counts["Administration"], 1)
        self.assertEqual(counts["Marketing"], 0)
        self.assertEqual(len(ceo["recent_clients"]), 2)
        self.assertTrue(any(s["full_name"] == "ceo" for s in ceo["recent_sign_ins"]))
        self.assertNotIn("operation", res.data)

    def test_operation_head_sees_client_numbers_only(self):
        self.login(self.ops)
        res = self.client.get("/api/dashboard/summary/")
        self.assertEqual(res.data["operation"]["total_clients"], 2)
        self.assertEqual(res.data["operation"]["clients_this_month"], 2)
        self.assertNotIn("ceo", res.data)
        self.assertEqual(len(res.data["my_sign_ins"]), 1)

    def test_everyone_else_only_gets_their_own_sign_ins(self):
        self.login(self.member)
        res = self.client.get("/api/dashboard/summary/")
        self.assertEqual(set(res.data), {"my_sign_ins"})
        self.assertEqual(len(res.data["my_sign_ins"]), 1)

    def test_blocked_while_password_change_is_pending_and_for_anonymous(self):
        self.assertEqual(self.client.get("/api/dashboard/summary/").status_code, 401)
        self.login(self.pending)
        self.assertEqual(self.client.get("/api/dashboard/summary/").status_code, 403)
