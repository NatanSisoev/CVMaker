"""
Base settings — shared across every environment.

Environment-specific overrides live in ``dev.py``, ``prod.py``, and ``test.py``.
Anything here should be the same in every environment; anything that differs
belongs in the env-specific module.
"""
from __future__ import annotations

import sys
from pathlib import Path

import environ

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
# settings/base.py → settings/ → cvmaker/ → src/ → repo root
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
APPS_DIR = BASE_DIR / "apps"
SRC_DIR = BASE_DIR / "src"

# Make the `apps/` directory importable so installed apps can be referenced
# by their short names (`accounts`, `cv`, `entries`, ...) rather than
# `apps.accounts` etc. Keeps app labels stable across the Phase 1 move.
if str(APPS_DIR) not in sys.path:
    sys.path.insert(0, str(APPS_DIR))

# ----------------------------------------------------------------------
# Environment
# ----------------------------------------------------------------------
env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    DB_PORT=(str, "5432"),
)

# Load .env from the repo root if present. In production, env vars come from
# the process environment directly and this call is a no-op.
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

# ----------------------------------------------------------------------
# Core — required in every environment
# ----------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")

# DEBUG defaults to False; dev.py flips it on. Never set DEBUG=True here.
DEBUG = False

# ----------------------------------------------------------------------
# Applications
# ----------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "widget_tweaks",
    "crispy_forms",
]

LOCAL_APPS = [
    "core",            # shared mixins / base models (apps/core)
    "accounts",        # custom User (apps/accounts)
    "cv",              # CV aggregate + Info / Design / Locale / Settings
    # Template tags in cv/templatetags/ are auto-discovered because `cv`
    # itself is installed -- no separate entry needed.
    "sections",        # ordered collections of entries
    "entries",         # polymorphic entry types
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ----------------------------------------------------------------------
# Custom user model (Phase 1.5). Must be set before the first migration.
# ----------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

# ----------------------------------------------------------------------
# Middleware
# ----------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cvmaker.urls"
WSGI_APPLICATION = "cvmaker.wsgi.application"
ASGI_APPLICATION = "cvmaker.asgi.application"

# ----------------------------------------------------------------------
# Templates
# ----------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.media",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ----------------------------------------------------------------------
# Database
# Prefer DATABASE_URL; fall back to individual DB_* vars for local dev.
# dev.py and test.py may override.
# ----------------------------------------------------------------------
if "DATABASE_URL" in env.ENVIRON:
    DATABASES = {"default": env.db_url("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", default="cvmaker"),
            "USER": env("DB_USER", default="postgres"),
            "PASSWORD": env("DB_PASSWORD", default=""),
            "HOST": env("DB_HOST", default="localhost"),
            "PORT": env("DB_PORT"),
        }
    }

# ----------------------------------------------------------------------
# Password validation
# ----------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "login"

# ----------------------------------------------------------------------
# i18n / tz
# ----------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

# ----------------------------------------------------------------------
# Static / media
# Static sources live in `static/src/` (Tailwind input, Phase 4); built
# assets land in `static/dist/` which is gitignored. collectstatic bundles
# everything into STATIC_ROOT for whitenoise.
# ----------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ----------------------------------------------------------------------
# Email
# dev.py defaults to the console backend; prod.py flips to SMTP/anymail.
# ----------------------------------------------------------------------
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="CVMaker <noreply@cvmaker.local>")

# ----------------------------------------------------------------------
# Misc
# ----------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CRISPY_TEMPLATE_PACK = "bootstrap5"                  # Phase 4 replaces with cotton

# Size limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024        # 5 MiB — photos for CVs
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ----------------------------------------------------------------------
# Logging — single JSON handler to stderr. dev.py replaces with a prettier
# console formatter. Phase 8 adds structlog + Sentry.
# ----------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "[{asctime}] {levelname} {name} — {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "cvmaker": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
