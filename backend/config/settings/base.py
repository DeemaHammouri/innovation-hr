"""Settings shared by every environment. development, test and production import this and override what differs."""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_list(name, default=""):
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me-0123456789")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "django_filters",
    "rest_framework_simplejwt.token_blacklist",
    "core",
    "accounts",
    "clients",
    "audit",
    "notifications",
    "files",
    "documents",
    "meetings",
    "comments",
    "lookups",
    "leads",
    "appointments",
    "quotations",
    "contracts",
    "operations",
    "payments",
    "hr",
    "reports",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# SQLite for dev. Set DB_ENGINE=postgres (plus DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT) for Postgres.
if os.environ.get("DB_ENGINE") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "innovation"),
            "USER": os.environ.get("DB_USER", "innovation"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.environ.get("DJANGO_DB_PATH", BASE_DIR / "db.sqlite3")}}

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "en-us"
# Database values are always stored in UTC. This is only the zone used for "today", months and attendance days.
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Amman")
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"

# Uploaded business files. Never exposed as a URL: they are only served by the authenticated download endpoint.
PRIVATE_MEDIA_ROOT = Path(os.environ.get("PRIVATE_MEDIA_ROOT", BASE_DIR / "private_media"))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["core.errors.EnvelopeJSONRenderer"],  # every error leaves as {"error": {"code", "message", "fields"?}}
    "DEFAULT_AUTHENTICATION_CLASSES": ["accounts.authentication.CookieJWTAuthentication"],
    # Fail closed: a view must declare the capabilities it needs (accounts/permissions.py), and nobody is stuck on the forced password change.
    "DEFAULT_PERMISSION_CLASSES": [
        "accounts.permissions.HasCapability",
        "accounts.permissions.PasswordChangeNotPending",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
}

# Tokens travel only in cookies (see accounts/authentication.py). Secure cookies need HTTPS; browsers still accept them on localhost.
AUTH_COOKIE_ACCESS = "access_token"
AUTH_COOKIE_REFRESH = "refresh_token"
AUTH_COOKIE_CSRF = "csrf_token"
AUTH_COOKIE_SECURE = os.environ.get("AUTH_COOKIE_SECURE", "0" if DEBUG else "1") == "1"
AUTH_COOKIE_SAMESITE = "Lax"
AUTH_REFRESH_COOKIE_PATH = "/api/v1/auth/"
AUTHENTICATION_BACKENDS = ["accounts.authentication.IdentifierBackend"]

# Sign-in lockout (see accounts/ratelimit.py): 5 wrong passwords in 5 minutes lock the account, 20 from one address lock the address.
# Honour X-Forwarded-For only behind a proxy you control that sets it.
LOGIN_MAX_FAILS_PER_EMAIL = 5
LOGIN_MAX_FAILS_PER_IP = 20
LOGIN_WINDOW_SECONDS = 5 * 60
TRUST_X_FORWARDED_FOR = os.environ.get("TRUST_X_FORWARDED_FOR", "0") == "1"

# Request bodies are small JSON or a single upload of at most 10 MB (files/views.py).
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024

# Never write passwords, tokens or Authorization headers to a log, whatever a future change logs by mistake.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"scrub": {"()": "core.logscrub.ScrubFilter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "filters": ["scrub"]}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}

# Days that are not working days when counting leave (Monday = 0). Friday and Saturday by default.
WEEKEND_DAYS = (4, 5)

# Passwords: Argon2 first (older hashes still verify and are upgraded at the next sign-in); the policy is in AUTH_PASSWORD_VALIDATORS.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
]

# Appointment reminders go out this long before the start (see notifications: process_notifications).
APPOINTMENT_REMINDER_MINUTES = 60

# Urgent alerts (notifications.urgent, run by process_notifications). Each is sent once per case, this many minutes after the trigger.
URGENT_HR_MINUTES = int(os.environ.get("URGENT_HR_MINUTES", "60"))  # HR: a quotation was assigned to them and still isn't submitted
URGENT_COMMERCIAL_MINUTES = int(os.environ.get("URGENT_COMMERCIAL_MINUTES", "60"))  # Commercial head: a quotation was submitted and still isn't signed
URGENT_APPOINTMENT_MINUTES = int(os.environ.get("URGENT_APPOINTMENT_MINUTES", "60"))  # the owner: an appointment's time passed and it is still open

# Email. Development prints messages in the terminal; production sets EMAIL_HOST (and friends) in the environment.
EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Innovation Accounting Solutions <no-reply@innovation.local>")
# Where a client opens the portal (used in the welcome email).
PORTAL_URL = os.environ.get("PORTAL_URL", "http://localhost:3000/portal")
