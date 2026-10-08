"""
Production settings.

DEBUG is always off here. HSTS, SSL redirect, secure cookies, and a
compressed-manifest static storage are required. Anything production needs
but dev doesn't (Sentry, real email provider, S3) is wired up here and
gated on its env var being present.
"""

from __future__ import annotations

from .base import *  # noqa: F403
from .base import (  # type: ignore[attr-defined]
    ANYMAIL,
    AWS_STORAGE_BUCKET_NAME,
    EMAIL_PROVIDER,
    LOGGING,
    _s3_storage_options,
    env,
)

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
# Object storage — S3 is mandatory in prod (Phase 3.5)
# ----------------------------------------------------------------------
if not AWS_STORAGE_BUCKET_NAME:
    raise RuntimeError(
        "AWS_STORAGE_BUCKET_NAME must be set in production "
        "(rendered PDFs and user uploads need somewhere to live)."
    )

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": _s3_storage_options(),
    },
    "staticfiles": {
        # Whitenoise still serves /static/ directly off the web container's
        # disk; we don't push collected static to S3 because the cache
        # behaviour and CSP story are simpler this way.
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

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
# Email -- EMAIL_PROVIDER (base.py) must be a real provider with its key.
# ----------------------------------------------------------------------
_PROVIDER_KEYS = {"resend": "RESEND_API_KEY", "postmark": "POSTMARK_SERVER_TOKEN"}
if EMAIL_PROVIDER == "console":
    raise RuntimeError("EMAIL_PROVIDER=console in production: set smtp, resend or postmark.")
if EMAIL_PROVIDER in _PROVIDER_KEYS and not ANYMAIL[_PROVIDER_KEYS[EMAIL_PROVIDER]]:
    raise RuntimeError(f"EMAIL_PROVIDER={EMAIL_PROVIDER} needs {_PROVIDER_KEYS[EMAIL_PROVIDER]}.")

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

# django-ratelimit lists only django-redis as "official"; Django's built-in
# RedisCache implements atomic incr(), which is all rate limiting needs.
SILENCED_SYSTEM_CHECKS = ["django_ratelimit.W001"]

if RENDER_INLINE:  # noqa: F405
    raise RuntimeError("RENDER_INLINE is a dev-only switch; production renders on the RQ worker.")
