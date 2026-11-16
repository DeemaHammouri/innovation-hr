"""Test runs: fast password hashing and a throwaway media folder. Used by `manage.py test` and by pytest."""
import tempfile
from pathlib import Path

from .base import *  # noqa: F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests only
PRIVATE_MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="innovation-test-media-"))
