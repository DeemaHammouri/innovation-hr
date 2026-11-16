"""`config.settings` is the development configuration. Pick another with DJANGO_SETTINGS_MODULE:
config.settings.production, config.settings.test (the test runners choose this one themselves)."""
from .development import *  # noqa: F401,F403
