"""P16: a notification is shown in the language its reader uses now, not the one they had when it was created."""
from rest_framework.test import APITestCase

from accounts.models import User
from notifications.models import Notification
from notifications.service import notify


class LanguageAtReadTimeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="u@x.com", password="x", full_name="U")
        self.client.force_authenticate(self.user)

    def listed(self):
        res = self.client.get("/api/notifications/")
        self.assertEqual(res.status_code, 200)
        return res.data["results"][0]

    def switch(self, lang):
        User.objects.filter(pk=self.user.pk).update(preferred_language=lang)
        self.user = User.objects.get(pk=self.user.pk)
        self.client.force_authenticate(self.user)

    def test_switching_to_arabic_changes_an_existing_notification(self):
        n = notify(self.user, "assigned", actor="Sam", ref="LD-1", name="Acme")
        self.assertEqual(self.listed()["title"], "Sam assigned you LD-1")
        self.switch("ar")
        item = self.listed()
        self.assertEqual(item["title"], "قام Sam بإسنادك إلى LD-1")
        self.assertEqual(item["body"], "Acme")
        self.switch("en")
        self.assertEqual(self.listed()["title"], "Sam assigned you LD-1")
        self.assertEqual(Notification.objects.get(pk=n.pk).title, "Sam assigned you LD-1")  # the stored first text is untouched

    def test_created_in_arabic_reads_in_english_after_the_switch(self):
        self.switch("ar")
        notify(self.user, "assigned", actor="Sam", ref="LD-2", name="Acme")
        self.assertIn("بإسنادك", self.listed()["title"])
        self.switch("en")
        self.assertEqual(self.listed()["title"], "Sam assigned you LD-2")

    def test_values_that_are_not_plain_text_survive_the_round_trip(self):
        import datetime

        notify(self.user, "gtask_overdue", ref="Report", name=datetime.date(2026, 6, 1))
        self.assertEqual(self.listed()["body"], "It was due 2026-06-01")

    def test_a_row_from_before_params_existed_keeps_its_stored_text(self):
        Notification.objects.create(user=self.user, kind="assigned", title="Old English title", body="Old body", params=None)
        self.switch("ar")
        item = self.listed()
        self.assertEqual((item["title"], item["body"]), ("Old English title", "Old body"))

    def test_an_unknown_kind_does_not_break_the_list(self):
        notify(self.user, "no_such_kind", ref="x")
        self.assertEqual(self.listed()["kind"], "no_such_kind")

    def test_only_the_readers_own_notifications_are_listed(self):
        other = User.objects.create_user(email="o@x.com", password="x", full_name="O")
        notify(other, "assigned", actor="Sam", ref="LD-3", name="Acme")
        self.assertEqual(self.client.get("/api/notifications/").data["results"], [])
