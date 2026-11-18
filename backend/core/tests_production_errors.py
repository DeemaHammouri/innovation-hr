"""The production settings must keep the error envelope: every 400/401/403/404/405/429 leaves as {"error": {"code", "message", "fields"?}}.

DRF reads its renderer classes when a view module is imported, so overriding settings inside a running test cannot show what production
does. These tests therefore start a fresh process with DJANGO_SETTINGS_MODULE=config.settings.production (and the environment that
module demands) and run the envelope checks of `accounts.tests_users_security.ErrorEnvelopeTests` in it. A plain DRF JSONRenderer in
production answers {"detail": "..."} and fails them.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

BACKEND = Path(__file__).resolve().parent.parent

PRODUCTION_ENV = {
    "DJANGO_SECRET_KEY": "k" * 60,
    "DJANGO_ALLOWED_HOSTS": "api.example.test",
    "CORS_ALLOWED_ORIGINS": "https://app.example.test",
    "SECURE_SSL_REDIRECT": "0",  # the test client speaks plain HTTP
}


class ProductionErrorEnvelopeTests(SimpleTestCase):
    def test_400_401_403_404_405_429_and_500_use_the_envelope_under_production_settings(self):
        env = {**os.environ, **PRODUCTION_ENV, "DJANGO_SETTINGS_MODULE": "config.settings.production"}
        if env.get("DB_ENGINE") == "postgres":  # the outer run owns the test database of the same name
            env["DB_NAME"] = env.get("DB_NAME", "innovation") + "_production_errors"
        with tempfile.TemporaryDirectory() as cache_dir, tempfile.TemporaryDirectory() as media_dir:
            env["DJANGO_CACHE_DIR"] = cache_dir
            env["PRIVATE_MEDIA_ROOT"] = media_dir
            done = subprocess.run(
                [sys.executable, "manage.py", "test", "accounts.tests_users_security.ErrorEnvelopeTests", "--noinput"],
                cwd=BACKEND, env=env, capture_output=True, text=True, timeout=600,
            )
        output = done.stdout + done.stderr
        self.assertEqual(done.returncode, 0, output[-3000:])
        self.assertIn("Ran 8 tests", output)  # 400 (fields), 401, 403, 404, 405, 429, 500 and the whole-API sweep
