"""Fix 3: a missing company stamp is a setup step to tell people about, not a failure to discover while signing."""
from core.models import CompanyProfile
from core.testing import RoleCase, ensure_stamp


class StampSetupTests(RoleCase):
    def test_every_signed_in_role_can_ask_but_only_the_ceo_can_manage(self):
        ensure_stamp()
        self.assert_matrix("get", "/api/company/setup/", {"*": 200})
        self.as_role("ceo")
        self.assertEqual(self.client.get("/api/company/setup/").data, {"has_stamp": True, "can_manage": True})
        self.as_role("hr_head")
        self.assertEqual(self.client.get("/api/company/setup/").data, {"has_stamp": True, "can_manage": False})

    def test_it_reports_a_missing_stamp_and_turns_green_after_the_upload(self):
        p = CompanyProfile.get()
        if p.stamp:
            p.stamp.delete(save=True)
        self.as_role("commercial_head")
        self.assertEqual(self.client.get("/api/company/setup/").data["has_stamp"], False)
        ensure_stamp()
        self.assertEqual(self.client.get("/api/company/setup/").data["has_stamp"], True)

    def test_signed_out_gets_401_and_the_endpoint_never_leaks_the_stamp_itself(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/company/setup/").status_code, 401)
        self.as_role("hr_head")
        self.assertEqual(self.client.get("/api/company/stamp/").status_code, 403)
