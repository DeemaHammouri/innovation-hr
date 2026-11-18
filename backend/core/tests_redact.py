"""P29: Operation never reads an amount typed into a free-text field; everybody else reads the text unchanged."""
from django.test import SimpleTestCase

from clients.models import Client
from comments.models import Comment
from core.access import content_type_for
from core.redact import mask_money
from operations.tests_handover import HCase

HIDDEN = "[amount hidden]"


class MaskMoneyTests(SimpleTestCase):
    def test_amounts_next_to_a_currency_are_hidden(self):
        for text in ("Price 7500 JD", "JD 7,500", "USD 1200.50", "$900", "we agreed 12k JOD", "7500 دينار", "دينار 7500", "5 ألف دينار", "€ 3 000"):
            masked = mask_money(text)
            self.assertIn(HIDDEN, masked, text)
            self.assertFalse(any(ch.isdigit() for ch in masked.replace("[amount hidden]", "")), (text, masked))

    def test_numbers_written_like_money_are_hidden_without_a_currency(self):
        for text in ("total 1,500", "total 1,500.75", "fee 12.50", "monthly 5000", "٧٥٠٠", "١٢٫٥٠"):
            self.assertIn(HIDDEN, mask_money(text), text)

    def test_what_operation_needs_is_left_alone(self):
        for text in ("Call Sam on +962791234567", "Phone 0791234567", "Ref QT/2026/11/0001 and CT-2026-0007", "Visit twice a month, 3 people, 10 hours",
                     "Starts 2026-12-01", "since 2024", "Floor 12, office 5", "Version 3.5", "Monthly bookkeeping"):
            self.assertEqual(mask_money(text), text)

    def test_the_marker_follows_the_readers_language(self):
        self.assertIn("[مبلغ مخفي]", mask_money("السعر 7500 دينار", "ar"))

    def test_empty_values_pass_through(self):
        self.assertEqual(mask_money(""), "")
        self.assertIsNone(mask_money(None))


class OperationNeverSeesAnAmountTests(HCase):
    NOTE = "Agreed 7,500 JD plus 1200.50 setup, 5000 retainer; call +962791234567, ref QT/2026/11/0001"

    def assertHidden(self, text):
        self.assertIn(HIDDEN, text)
        for leaked in ("7,500", "1200", "5000", "7500"):
            self.assertNotIn(leaked, text)
        self.assertIn("+962791234567", text)  # the contact number survives
        self.assertIn("QT/2026/11/0001", text)  # so does the reference

    def test_handover_text_is_masked_for_operation_and_untouched_for_commercial(self):
        h = self.filled()
        saved = self.call(self.cmem, h, "save", {"services": self.NOTE, "scope_notes": self.NOTE, "contacts": self.NOTE, "special_requirements": self.NOTE})
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(self.call(self.cmem, h, "submit").status_code, 200)
        self.as_user(self.omem)
        seen = self.client.get(f"/api/handovers/{h.pk}/")
        self.assertEqual(seen.status_code, 200, seen.data)
        for field in ("services", "scope_notes", "contacts", "special_requirements"):
            self.assertHidden(seen.data[field])
        self.as_user(self.cmem)
        own = self.client.get(f"/api/handovers/{h.pk}/")
        for field in ("services", "scope_notes", "contacts", "special_requirements"):
            self.assertEqual(own.data[field], self.NOTE)  # the author reads exactly what was written
        h.refresh_from_db()
        self.assertEqual(h.services, self.NOTE)  # and the stored text was never altered

    def test_client_notes_and_comments_are_masked_for_operation_only(self):
        h = self.filled()
        client = h.client
        Client.objects.filter(pk=client.pk).update(notes=self.NOTE, decision_note=self.NOTE)
        Comment.objects.create(author=self.cmem, content_type=content_type_for(Client), object_id=client.pk, body=self.NOTE)

        self.as_user(self.ohead)  # the Operation head may open the client record
        detail = self.client.get(f"/api/clients/{client.pk}/")
        self.assertEqual(detail.status_code, 200)
        self.assertHidden(detail.data["notes"])
        self.assertHidden(detail.data["decision_note"])
        self.as_user(self.ceo)
        detail = self.client.get(f"/api/clients/{client.pk}/")
        self.assertEqual((detail.data["notes"], detail.data["decision_note"]), (self.NOTE, self.NOTE))

        for user, masked in ((self.omem, True), (self.ohead, True), (self.cmem, False), (self.ceo, False)):
            self.as_user(user)
            res = self.client.get(f"/api/comments/?target=client:{client.pk}")
            self.assertEqual(res.status_code, 200, user.email)
            body = res.data["results"][0]["body"]
            if masked:
                self.assertHidden(body)
            else:
                self.assertEqual(body, self.NOTE, user.email)
