"""TubeForge AI backend settings.

Required env vars (fail fast with ImproperlyConfigured when missing):
  SECRET_KEY   - Django secret key. No default, ever.
  FERNET_KEY   - Fernet key used to encrypt secrets at rest. Validated at startup.
  DATABASE_URL - postgres:// URL. Not required when TESTING=true (sqlite :memory:).
"""
import os
from urllib.parse import urlparse, unquote

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and (value is None or value == ""):
        raise ImproperlyConfigured(f"Required environment variable {name} is not set.")
    return value


def env_bool(name, default="False"):
    return str(env(name, default)).lower() in ("1", "true", "yes", "on")


SECRET_KEY = env("SECRET_KEY", required=True)
FERNET_KEY = env("FERNET_KEY", required=True)
try:
    Fernet(FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY)
except Exception as exc:  # pragma: no cover - startup guard
    raise ImproperlyConfigured(f"FERNET_KEY is not a valid Fernet key: {exc}")

DEBUG = env_bool("DEBUG", "False")
ALLOWED_HOSTS = [h.strip() for h in env("ALLOWED_HOSTS", "localhost").split(",") if h.strip()]
TESTING = env_bool("TESTING", "False")


def _database_config():
    if TESTING:
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
    url = env("DATABASE_URL", required=True)
    parts = urlparse(url)
    if parts.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("DATABASE_URL must be a postgres:// or postgresql:// URL.")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parts.path.lstrip("/") or "tubeforge",
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "localhost",
        "PORT": parts.port or 5432,
    }


DATABASES = {"default": _database_config()}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework.authtoken",
    "core",
    "channels",
    "research",
    "projects",
    "providers",
    "workflows",
    "publishing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.utils.CorrelationIdMiddleware",
]

ROOT_URLCONF = "config.urls"
APPEND_SLASH = False

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

AUTH_USER_MODEL = "core.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "core.utils.tubeforge_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "core.utils.TubeForgePagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "200/day",
        "user": "5000/day",
        "login": "10/minute",
    },
}

# --- TubeForge integrations (all optional) ---------------------------------
REDIS_URL = env("REDIS_URL", "")
TEMPORAL_HOST = env("TEMPORAL_HOST", "localhost:7233")
TEMPORAL_NAMESPACE = env("TEMPORAL_NAMESPACE", "default")
TEMPORAL_TASK_QUEUE = env("TEMPORAL_TASK_QUEUE", "tubeforge-video")

YOUTUBE_CLIENT_ID = env("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = env("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REDIRECT_URI = env("YOUTUBE_REDIRECT_URI", "")

FRONTEND_URL = env("FRONTEND_URL", "")
PUBLIC_APP_URL = env("PUBLIC_APP_URL", "")

S3_ENDPOINT = env("S3_ENDPOINT", "")
S3_ACCESS_KEY = env("S3_ACCESS_KEY", "")
S3_SECRET_KEY = env("S3_SECRET_KEY", "")
S3_BUCKET = env("S3_BUCKET", "")
S3_REGION = env("S3_REGION", "us-east-1")

AI_WORKER_CONCURRENCY = int(env("AI_WORKER_CONCURRENCY", "2"))

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
