"""
Production settings.

DEBUG is always off here. HSTS, SSL redirect, secure cookies, and a
compressed-manifest static storage are required. Anything production needs
but dev doesn't (Sentry, real email provider, S3) is wired up here and
gated on its env var being present.
"""

from __future__ import annotations

from .base import *  # noqa: F403
from .base import LOGGING, env  # type: ignore[attr-defined]

# ----------------------------------------------------------------------
# Core — strict
# ----------------------------------------------------------------------
DEBUG = False

# Prod must always have an explicit ALLOWED_HOSTS — the default "[]" on
# base triggers a clean ImproperlyConfigured when someone forgets.
if not env("DJANGO_ALLOWED_HOSTS"):
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must be set in production (comma-separated list).")

# ----------------------------------------------------------------------
# Security headers
# ----------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=31_536_000)  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# ----------------------------------------------------------------------
# Cache — Redis
# ----------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://redis:6379/0"),
    },
}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# ----------------------------------------------------------------------
# Email — plug in anymail provider in Phase 6
# ----------------------------------------------------------------------
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)

# ----------------------------------------------------------------------
# Logging — JSON for log aggregators
# ----------------------------------------------------------------------
LOGGING["formatters"]["json"] = {
    "()": "logging.Formatter",
    "format": (
        '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)r}'
    ),
}
LOGGING["handlers"]["console"]["formatter"] = "json"
