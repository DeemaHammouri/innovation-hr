"""Objective 13: a lead that gets the initial acceptance becomes a client, the lead is frozen, and the client gets a portal login."""
from unittest import mock

from django.core import mail

from accounts.models import Role, User
from clients.models import Client
from core import permission_audit
from core.tests_capabilities import PUBLIC_VIEWS, needs
from leads.models import Lead
from leads.tests import LeadCase


class ConversionCase(LeadCase):
    def accept(self, lead, user=None):
        self.as_user(user or self.head)
        return self.client.post(f"/api/leads/{lead.pk}/interactions/", {"type": "call", "outcome": "accepted"}, format="json")

    def converted(self, **over):
        over.setdefault("email", "owner@acme.example")
        over.setdefault("contact_name", "Dana Owner")
        lead = self.mk(assigned=self.member, **over)
        self.assertEqual(self.accept(lead).status_code, 201)
        return lead, Client.objects.get(lead=lead)


class ConversionTests(ConversionCase):
    def test_acceptance_creates_one_client_linked_to_the_lead(self):
        lead, client = self.converted()
        self.assertEqual((client.company_name, client.contact_person, client.email, client.status), (lead.company_name, "Dana Owner", "owner@acme.example", "prospect"))
        self.assertEqual(Client.objects.filter(lead=lead).count(), 1)
        lead.refresh_from_db()
        self.assertEqual(lead.status, "qualified")

    def test_other_outcomes_do_not_convert(self):
        lead = self.mk(assigned=self.member)
        self.as_user(self.head)
        self.client.post(f"/api/leads/{lead.pk}/interactions/", {"type": "call", "outcome": "waiting", "next_follow_up": self.day(3)}, format="json")
        self.assertEqual(Client.objects.count(), 0)

    def test_the_lead_is_locked_with_409_lead_converted(self):
        lead, _ = self.converted()
        self.as_user(self.head)
        url = f"/api/leads/{lead.pk}"
        attempts = [
            ("patch", f"{url}/", {"company_name": "Renamed"}),
            ("post", f"{url}/archive/", {"reason": "x"}),
            ("post", f"{url}/assign/", {"assigned_to": self.member2.pk}),
            ("post", f"{url}/interactions/", {"type": "call", "outcome": "rejected"}),
            ("post", f"{url}/outcome/", {"outcome": "rejected"}),
            ("post", f"{url}/reopen/", {"note": "again"}),
        ]
        for method, path, body in attempts:
            res = getattr(self.client, method)(path, body, format="json")
            self.assertEqual(res.status_code, 409, path)
            self.assertEqual(res.json()["error"]["code"], "lead_converted", path)
        lead.refresh_from_db()
        self.assertEqual((lead.status, lead.company_name), ("qualified", f"Company {self.n}"))

    def test_the_screen_is_told_not_to_offer_any_change(self):
        lead, client = self.converted()
        self.as_user(self.head)
        data = self.client.get(f"/api/leads/{lead.pk}/").data
        self.assertEqual(data["client_id"], client.pk)
        self.assertFalse(any(data["permissions"][k] for k in ("can_edit", "can_assign", "can_log", "can_reopen", "can_archive", "can_restore")))

    def test_the_quotation_path_still_works_after_conversion(self):
        lead, _ = self.converted()
        self.as_user(self.head)
        self.assertEqual(self.client.post(f"/api/leads/{lead.pk}/skip-quotation/", {}, format="json").status_code, 200)

    def test_the_handover_reuses_the_converted_client_and_starts_onboarding(self):
        from operations import services as ops

        lead, client = self.converted()
        contract = mock.Mock(lead=lead)
        contract.save = mock.Mock()
        with mock.patch("operations.services.record"):
            got = ops.onboard(self.head, contract)
        client.refresh_from_db()
        self.assertEqual((got.pk, client.status), (client.pk, "onboarding"))
        self.assertEqual(Client.objects.count(), 1)

    def test_a_failure_while_converting_rolls_the_acceptance_back(self):
        lead = self.mk(assigned=self.member, email="x@y.example")
        self.client.raise_request_exception = False
        with mock.patch("clients.services.Client.objects.create", side_effect=RuntimeError("boom")):
            res = self.accept(lead)
        self.assertEqual(res.status_code, 500)
        lead.refresh_from_db()
        self.assertEqual((lead.status, Client.objects.count()), ("new", 0))


class PortalAccountTests(ConversionCase):
    def test_account_is_made_and_the_temporary_password_is_emailed(self):
        _, client = self.converted()
        user = client.portal_user
        self.assertEqual((client.portal_status, user.email, user.role_ref.key, user.must_change_password), ("sent", "owner@acme.example", "client", True))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["owner@acme.example"])
        body = mail.outbox[0].body
        self.assertIn("Temporary password:", body)
        password = body.split("Temporary password: ")[1].split("\n")[0]
        self.assertTrue(user.check_password(password))
        self.assertNotIn(password, "".join(str(a.to_value) for a in __import__("audit.models", fromlist=["AuditEntry"]).AuditEntry.objects.all()))

    def test_missing_email_still_converts_and_says_so(self):
        _, client = self.converted(email="", phone="0791110022")
        self.assertEqual((client.portal_status, client.portal_user_id, len(mail.outbox)), ("no_email", None, 0))

    def test_email_already_in_use_still_converts_and_says_so(self):
        _, client = self.converted(email=self.member.email)
        self.assertEqual((client.portal_status, client.portal_user_id, len(mail.outbox)), ("email_in_use", None, 0))
        self.assertEqual(User.objects.filter(email=self.member.email).count(), 1)

    def test_a_mail_server_failure_does_not_undo_the_conversion(self):
        with mock.patch("clients.services.send_mail", side_effect=OSError("smtp down")):
            _, client = self.converted()
        self.assertEqual(client.portal_status, "failed")
        self.assertTrue(client.portal_user_id)

    def test_staff_can_open_the_portal_after_fixing_the_email_and_resend(self):
        _, client = self.converted(email="", phone="0791110033")
        self.as_role("operation_head")
        self.assertEqual(self.client.patch(f"/api/clients/{client.pk}/", {"email": "late@acme.example"}, format="json").status_code, 200)
        res = self.client.post(f"/api/clients/{client.pk}/portal/")
        self.assertEqual((res.status_code, res.data["portal_status"]), (200, "sent"))
        first = User.objects.get(email="late@acme.example")
        old = first.password
        res = self.client.post(f"/api/clients/{client.pk}/portal/")
        first.refresh_from_db()
        self.assertEqual(res.data["portal_status"], "sent")
        self.assertNotEqual(first.password, old)
        self.assertTrue(first.must_change_password)
        self.assertEqual(len(mail.outbox), 2)

    def test_only_client_managers_can_resend(self):
        _, client = self.converted()
        self.assert_matrix("post", f"/api/clients/{client.pk}/portal/", {"ceo": 200, "operation_head": 200, "*": 403})


class PortalAccessTests(ConversionCase):
    def setUp(self):
        super().setUp()
        _, self.c1 = self.converted(email="one@acme.example")
        _, self.c2 = self.converted(email="two@acme.example", phone="0791110044")
        self.u1, self.u2 = self.c1.portal_user, self.c2.portal_user
        User.objects.filter(pk__in=[self.u1.pk, self.u2.pk]).update(must_change_password=False)  # they have chosen their own passwords
        self.u1.refresh_from_db()
        self.u2.refresh_from_db()

    def test_a_client_sees_only_their_own_company(self):
        self.as_user(self.u1)
        res = self.client.get("/api/portal/me/")
        self.assertEqual((res.status_code, res.data["client"]["id"]), (200, self.c1.pk))
        self.as_user(self.u2)
        self.assertEqual(self.client.get("/api/portal/me/").data["client"]["id"], self.c2.pk)

    def test_staff_cannot_open_the_portal_and_a_client_has_no_staff_pages(self):
        self.assert_matrix("get", "/api/portal/me/", {"*": 403})
        self.as_user(self.u1)
        for url in ("/api/clients/", f"/api/clients/{self.c2.pk}/", "/api/leads/", "/api/quotations/", "/api/contracts/", "/api/users/", "/api/operations/clients/", "/api/payments/"):
            self.assertIn(self.client.get(url).status_code, (403, 404), url)

    def test_a_client_can_reach_nothing_a_staff_capability_guards(self):
        self.as_user(self.u1)
        leaks = []
        for url, _ in permission_audit.endpoints():
            for method in permission_audit.METHODS:
                needed, view = needs(method, url)
                if needed == "no-handler" or needed in ([], ["portal.access"]) or type(view).__name__ in PUBLIC_VIEWS:
                    continue
                code = permission_audit.call(self.client, method, url).status_code
                if code not in (401, 403, 404, 405):
                    leaks.append(f"{method.upper()} {url} -> {code}")
        self.assertEqual(leaks, [], "\n".join(leaks[:20]))

    def test_client_accounts_never_appear_in_user_management(self):
        self.as_role("ceo")
        data = self.client.get("/api/users/?page_size=100").data
        emails = [u["email"] for u in (data["results"] if isinstance(data, dict) else data)]
        self.assertNotIn("one@acme.example", emails)
        self.assertNotIn("client", [r["key"] for r in self.client.get("/api/roles/").data])
        self.assertEqual(self.client.get(f"/api/users/{self.u1.pk}/").status_code, 404)

    def test_first_sign_in_forces_a_new_password(self):
        _, fresh = self.converted(email="fresh@acme.example", phone="0791110055")
        user = fresh.portal_user
        self.assertTrue(user.must_change_password)
        self.as_user(user)
        self.assertEqual(self.client.get("/api/portal/me/").status_code, 403)  # blocked until the password is changed
        res = self.client.get("/api/auth/me/")
        self.assertEqual((res.status_code, res.data["role_key"], res.data["must_change_password"]), (200, "client", True))
