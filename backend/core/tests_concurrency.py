import time

from clients.models import Client
from core.concurrency import MSG_CONFLICT
from core.testing import RoleCase
from leads.models import Lead


class StaleEditTests(RoleCase):
    """Two people open the same edit form; the second save must be refused with a clear message, not silently overwrite."""

    def test_client_second_save_gets_a_conflict(self):
        self.as_role("operation_head")
        created = self.client.post("/api/clients/", {"company_name": "Alpha Co"}, format="json").data
        time.sleep(0.03)  # the Windows clock can tick coarsely; two saves in one tick would share an updated_at
        first = self.client.patch(f"/api/clients/{created['id']}/", {"phone": "0791", "expected_updated_at": created["updated_at"]}, format="json")
        self.assertEqual(first.status_code, 200)
        time.sleep(0.03)
        second = self.client.patch(f"/api/clients/{created['id']}/", {"phone": "0792", "expected_updated_at": created["updated_at"]}, format="json")
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data["detail"], MSG_CONFLICT)
        self.assertEqual(Client.objects.get(pk=created["id"]).phone, "0791")

    def test_client_with_the_fresh_token_saves_again(self):
        self.as_role("operation_head")
        created = self.client.post("/api/clients/", {"company_name": "Alpha Co"}, format="json").data
        first = self.client.patch(f"/api/clients/{created['id']}/", {"phone": "0791", "expected_updated_at": created["updated_at"]}, format="json").data
        again = self.client.patch(f"/api/clients/{created['id']}/", {"phone": "0793", "expected_updated_at": first["updated_at"]}, format="json")
        self.assertEqual(again.status_code, 200)

    def test_no_token_means_no_check(self):
        self.as_role("operation_head")
        created = self.client.post("/api/clients/", {"company_name": "Alpha Co"}, format="json").data
        self.assertEqual(self.client.patch(f"/api/clients/{created['id']}/", {"phone": "0791"}, format="json").status_code, 200)

    def test_garbage_token_is_a_conflict_not_a_crash(self):
        self.as_role("operation_head")
        created = self.client.post("/api/clients/", {"company_name": "Alpha Co"}, format="json").data
        res = self.client.patch(f"/api/clients/{created['id']}/", {"phone": "1", "expected_updated_at": "not-a-date"}, format="json")
        self.assertEqual(res.status_code, 409)

    def test_lead_second_save_gets_a_conflict(self):
        lead = Lead.objects.create(company_name="Lead Co", phone="0790000001", created_by=self.users["marketing"], assigned_to=self.users["commercial_member"], status="contacted")
        self.as_role("commercial_member")
        token = self.client.get(f"/api/leads/{lead.pk}/").data["updated_at"]
        ok = self.client.patch(f"/api/leads/{lead.pk}/", {"notes": "first", "expected_updated_at": token}, format="json")
        self.assertEqual(ok.status_code, 200, ok.data)
        stale = self.client.patch(f"/api/leads/{lead.pk}/", {"notes": "second", "expected_updated_at": token}, format="json")
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(Lead.objects.get(pk=lead.pk).notes, "first")


class FrozenClockTests(RoleCase):
    """The worst case of a coarse clock (Windows ticks about every 15 ms): time does not move at all between saves.
    Every saved version must still have its own `updated_at`, or a stale edit looks fresh."""

    def freeze(self):
        from unittest import mock

        from django.utils import timezone

        return mock.patch("django.utils.timezone.now", return_value=timezone.now())

    def test_updated_at_moves_forward_on_every_save_even_if_the_clock_stands_still(self):
        with self.freeze():
            lead = Lead.objects.create(company_name="Lead Co", phone="0790000001", created_by=self.users["marketing"])
            seen = [lead.updated_at]
            for i in range(4):
                lead.notes = f"edit {i}"
                lead.save()
                seen.append(lead.updated_at)
        self.assertEqual(seen, sorted(set(seen)), "each save must give a later timestamp than the one before")
        self.assertEqual(Lead.objects.get(pk=lead.pk).updated_at, seen[-1])

    def test_a_stale_edit_is_refused_when_the_clock_stands_still(self):
        with self.freeze():
            lead = Lead.objects.create(company_name="Lead Co", phone="0790000002", created_by=self.users["marketing"], assigned_to=self.users["commercial_member"], status="contacted")
            self.as_role("commercial_member")
            token = self.client.get(f"/api/leads/{lead.pk}/").data["updated_at"]
            ok = self.client.patch(f"/api/leads/{lead.pk}/", {"notes": "first", "expected_updated_at": token}, format="json")
            stale = self.client.patch(f"/api/leads/{lead.pk}/", {"notes": "second", "expected_updated_at": token}, format="json")
        self.assertEqual((ok.status_code, stale.status_code), (200, 409))
        self.assertEqual(Lead.objects.get(pk=lead.pk).notes, "first")

    def test_the_same_holds_for_clients(self):
        with self.freeze():
            self.as_role("operation_head")
            created = self.client.post("/api/clients/", {"company_name": "Alpha Co"}, format="json").data
            first = self.client.patch(f"/api/clients/{created['id']}/", {"phone": "0791", "expected_updated_at": created["updated_at"]}, format="json")
            second = self.client.patch(f"/api/clients/{created['id']}/", {"phone": "0792", "expected_updated_at": created["updated_at"]}, format="json")
        self.assertEqual((first.status_code, second.status_code), (200, 409))
