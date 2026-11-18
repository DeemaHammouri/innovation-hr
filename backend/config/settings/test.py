"""Test runs: fast password hashing and a throwaway media folder. Used by `manage.py test` and by pytest."""
import tempfile
from pathlib import Path

from .base import *  # noqa: F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests only
PRIVATE_MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="innovation-test-media-"))

# A real database file, so tests that use several threads (concurrent inserts) behave like production: writers queue on the file lock
# instead of tripping over SQLite's shared in-memory cache. Only used when the engine is SQLite.
import os  # noqa: E402

if DATABASES["default"]["ENGINE"].endswith("sqlite3"):  # noqa: F405
    DATABASES["default"]["ENGINE"] = "config.sqlite_testdb"  # noqa: F405  # SQLite whose test flush may empty the append-only audit table
    DATABASES["default"]["TEST"] = {"NAME": str(Path(tempfile.gettempdir()) / f"innovation-test-{os.getpid()}.sqlite3")}  # noqa: F405
    DATABASES["default"].setdefault("OPTIONS", {}).update({"timeout": 20, "transaction_mode": "IMMEDIATE"})  # noqa: F405  # writers queue instead of failing with "database is locked"
