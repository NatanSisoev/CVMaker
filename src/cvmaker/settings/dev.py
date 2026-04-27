"""
Development settings.

Turn on DEBUG, wire in debug-toolbar, loosen a few knobs. Default loader
used by ``manage.py`` when ``DJANGO_SETTINGS_MODULE`` is unset.
"""

from __future__ import annotations

from .base import *  # noqa: F403
from .base import INSTALLED_APPS, MIDDLEWARE, env  # type: ignore[attr-defined]

# ----------------------------------------------------------------------
# Core
# ----------------------------------------------------------------------
DEBUG = True
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "0.0.0.0"])

# In dev, turn off whitenoise's compressed-manifest storage; it breaks
# the runserver static file lookup for files that aren't yet collected.
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
