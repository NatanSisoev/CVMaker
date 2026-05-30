"""
Development settings.

Turn on DEBUG, wire in debug-toolbar, loosen a few knobs. Default loader
used by ``manage.py`` when ``DJANGO_SETTINGS_MODULE`` is unset.
"""

from __future__ import annotations

from .base import *  # noqa: F403
from .base import (  # type: ignore[attr-defined]
    AWS_S3_ENDPOINT_URL,
    INSTALLED_APPS,
    MIDDLEWARE,
    _s3_storage_options,
    env,
)

# ----------------------------------------------------------------------
# Core
# ----------------------------------------------------------------------
DEBUG = True
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "0.0.0.0"])

# Storage:
#   - staticfiles: turn off whitenoise's compressed-manifest variant; it
#     breaks the runserver lookup for files that aren't yet collected.
#   - default: MinIO (via django-storages S3 backend) when
#     ``AWS_S3_ENDPOINT_URL`` is set in the environment, otherwise the
#     local filesystem. Compose wires the env var, so ``compose up`` =
#     MinIO; bare ``runserver`` = filesystem.
if AWS_S3_ENDPOINT_URL:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": _s3_storage_options(),
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

# ----------------------------------------------------------------------
# Debug toolbar + extensions (dev only)
# ----------------------------------------------------------------------
INSTALLED_APPS = [
    *INSTALLED_APPS,
    "debug_toolbar",
    "django_extensions",
]

MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    *MIDDLEWARE,
]

INTERNAL_IPS = ["127.0.0.1", "::1"]


# Make the toolbar play nicely with Docker (`host.docker.internal`).
def _show_toolbar(request):
    return DEBUG


DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": "cvmaker.settings.dev._show_toolbar"}

# ----------------------------------------------------------------------
# Email — log to console in dev, no external SMTP
# ----------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ----------------------------------------------------------------------
# Cache — dummy cache in dev so stale entries never bite you
# ----------------------------------------------------------------------
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
}
