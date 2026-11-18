"""P8: editing a person's name or email must not sign them out; moving them to another seat must."""
from .models import User
from .tests import BaseCase


class TokenVersionOnUpdateTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.member = self.make("m@x.com", "Commercial", "member")
        self.login(self.ceo)

    def version(self, user):
        return User.objects.values_list("token_version", flat=True).get(pk=user.pk)

    def test_changing_only_the_name_keeps_the_persons_tokens(self):
        before = self.version(self.member)
        res = self.client.patch(f"/api/users/{self.member.pk}/", {"full_name": "New Name"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(User.objects.get(pk=self.member.pk).full_name, "New Name")
        self.assertEqual(self.version(self.member), before)

    def test_the_ceo_editing_their_own_name_is_not_signed_out(self):
        before = self.version(self.ceo)
        res = self.client.patch(f"/api/users/{self.ceo.pk}/", {"full_name": "Boss"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.version(self.ceo), before)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)

    def test_sending_the_same_department_and_role_changes_nothing(self):
        before = self.version(self.member)
        res = self.client.patch(f"/api/users/{self.member.pk}/", {"department": self.dept["Commercial"].pk, "role": "member", "full_name": "Same Seat"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.version(self.member), before)

    def test_a_new_role_still_cuts_off_the_old_tokens(self):
        before = self.version(self.member)
        res = self.client.patch(f"/api/users/{self.member.pk}/", {"role": "head"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.version(self.member), before + 1)

    def test_a_new_department_still_cuts_off_the_old_tokens(self):
        before = self.version(self.member)
        res = self.client.patch(f"/api/users/{self.member.pk}/", {"department": self.dept["HR"].pk, "role": "member"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.version(self.member), before + 1)
