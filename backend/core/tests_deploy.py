"""Deployment hygiene: every variable the code reads is documented, and no secret-looking value is committed."""
import re
import subprocess
from pathlib import Path

from django.test import SimpleTestCase, TestCase

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
READS = re.compile(r"""(?:environ(?:\.get\(|\[)|getenv\(|required\(|env_list\()["']([A-Z][A-Z0-9_]+)""")


class EnvDocumentationTests(SimpleTestCase):
    def test_every_environment_variable_is_in_env_example(self):
        documented = set(re.findall(r"^([A-Z][A-Z0-9_]+)=", (BACKEND / ".env.example").read_text(), re.M))
        used = set()
        for path in BACKEND.rglob("*.py"):
            if {".venv", "venv", "site-packages"} & set(path.parts) or "migrations" in path.parts or path.name.startswith(("tests", "test_")):
                continue
            used |= set(READS.findall(path.read_text(encoding="utf-8")))
        self.assertEqual(sorted(used - documented), [], "add these to backend/.env.example")

    def test_compose_publishes_only_the_frontend(self):
        text = (ROOT / "docker-compose.yml").read_text()
        self.assertEqual(len(re.findall(r"^\s+ports:", text, re.M)), 1)
        self.assertIn("healthcheck", text)


    def test_backend_healthchecks_send_an_allowed_host(self):
        """Production refuses Host 127.0.0.1 (DisallowedHost, 400), so the container checks must send a host from DJANGO_ALLOWED_HOSTS."""
        for name in ("docker-compose.yml", "backend/Dockerfile"):
            text = (ROOT / name).read_text()
            line = next(l for l in text.splitlines() if "/api/v1/health/" in l)
            self.assertIn("DJANGO_ALLOWED_HOSTS", line, f"{name}: the healthcheck must send a Host from DJANGO_ALLOWED_HOSTS")
            self.assertIn("'Host'", line, f"{name}: the healthcheck must set the Host header")

class HealthTests(TestCase):
    def test_health_endpoint_under_v1(self):
        res = self.client.get("/api/v1/health/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/api/health/").status_code, 200)
