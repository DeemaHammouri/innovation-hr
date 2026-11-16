"""Production settings. Use with:  DJANGO_SETTINGS_MODULE=config.settings.production

Starts only when the required environment variables are present and sane; it refuses to run with a guessable secret, with DEBUG on,
with no allowed hosts, or with the demo-data guard defeated. Everything not listed here is inherited from config.settings.base.
"""
import os

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env_list

from django.core.exceptions import ImproperlyConfigured


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"{name} must be set in production.")
    return value


DEBUG = False
os.environ["DJANGO_ENV"] = "production"  # seed_demo_data refuses to run

SECRET_KEY = required("DJANGO_SECRET_KEY")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("dev-only"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a long random value (50+ characters), never the development default.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must list the real host names (no '*').")

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
if not CORS_ALLOWED_ORIGINS or any(o.startswith("http://") for o in CORS_ALLOWED_ORIGINS):
    raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must list the https:// address(es) of the web app.")
CORS_ALLOW_CREDENTIALS = False  # the browser only talks to the same-origin Next.js proxy; no cross-origin cookie use
AUTH_COOKIE_SECURE = True  # sign-in cookies are never sent over plain HTTP
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# HTTPS everywhere. If TLS ends at a reverse proxy, set SECURE_PROXY_SSL=1 so Django trusts its X-Forwarded-Proto.
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
if os.environ.get("SECURE_PROXY_SSL", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# JSON only in production: no browsable API.
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"]}  # noqa: F405

# Sign-in lockout counters shared by all workers on this machine. Use Redis (django.core.cache.backends.redis.RedisCache) for several machines.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.filebased.FileBasedCache", "LOCATION": os.environ.get("DJANGO_CACHE_DIR", str(BASE_DIR / "cache"))}}

STATIC_ROOT = os.environ.get("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles"))
