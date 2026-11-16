"""
Permission test harness. Every access rule is tested against ALL eight roles, so a forgotten role fails loudly.

    class LeadAccess(RoleCase):
        def test_create(self):
            self.assert_matrix("post", "/api/leads/", {MARKETING_USER: 201, "*": 403}, data=payload)
"""
from rest_framework.test import APITestCase

from accounts.models import DEPARTMENT_NAMES, Department, User

from .roles import ALL_ROLES

PASSWORD = "role-pass-123"


def png_signature(blank=False):
    """What the signature pad sends: a PNG data URL. `blank=True` is an empty canvas."""
    import base64
    import io

    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (300, 120), (255, 255, 255, 0))
    if not blank:
        ImageDraw.Draw(img).line([(10, 90), (80, 20), (150, 100), (260, 30)], fill=(10, 20, 90, 255), width=4)
    out = io.BytesIO()
    img.save(out, "PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


def ensure_stamp():
    """The company stamp every signature needs. Safe to call twice."""
    import base64

    from django.core.files.base import ContentFile

    from core.models import CompanyProfile

    p = CompanyProfile.get()
    if not p.stamp:
        p.stamp.save("stamp.png", ContentFile(base64.b64decode(png_signature().split(",", 1)[1])))
    return p

# role key -> (department, head or member)
SEATS = {
    "ceo": ("Administration", "head"),
    "marketing": ("Marketing", "member"),
    "commercial_head": ("Commercial", "head"),
    "commercial_member": ("Commercial", "member"),
    "hr_head": ("HR", "head"),
    "hr_member": ("HR", "member"),
    "operation_head": ("Operation", "head"),
    "operation_member": ("Operation", "member"),
}


class RoleCase(APITestCase):
    def setUp(self):
        self.depts = {n: Department.objects.create(name=n) for n in DEPARTMENT_NAMES}
        self.users = {key: self.make_user(f"{key}@x.com", *seat) for key, seat in SEATS.items()}
        ensure_stamp()

    def make_user(self, email, dept, role="member", **extra):
        return User.objects.create_user(
            email=email, password=PASSWORD, full_name=email.split("@")[0].replace("_", " ").title(),
            department=self.depts[dept], role=role, **extra,
        )

    def as_role(self, key):
        user = self.users[key]
        user.capability_codes  # noqa: B018  (read once, so query-count tests measure the endpoint and not the capability lookup)
        self.client.force_authenticate(user)
        return user

    def as_user(self, user):
        user.capability_codes  # noqa: B018  (warm, as in as_role)
        self.client.force_authenticate(user)
        return user

    def call(self, method, url, data=None, fmt="json"):
        if method == "get":
            return self.client.get(url, data)
        return getattr(self.client, method)(url, data, format=fmt)

    def assert_matrix(self, method, url, expected, data=None, fmt="json"):
        """expected maps role key -> status code. "*" covers every role not listed."""
        default = expected.get("*")
        for key in ALL_ROLES:
            code = expected.get(key, default)
            self.assertIsNotNone(code, f"no expected status for role {key}")
            self.as_role(key)
            res = self.call(method, url, data, fmt)
            self.assertEqual(
                res.status_code, code,
                f"{method.upper()} {url} as {key}: got {res.status_code}, expected {code}. {getattr(res, 'data', '')}",
            )
        self.client.force_authenticate(None)
