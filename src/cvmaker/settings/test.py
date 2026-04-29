"""
Test settings.

SQLite in-memory for speed, migrations disabled for speed, password hasher
replaced with the cheapest option for speed. These settings exist solely to
make pytest runs fast and hermetic.
"""

from __future__ import annotations

from .base import *  # noqa: F403
from .base import MIDDLEWARE  # type: ignore[attr-defined]

# ----------------------------------------------------------------------
# Middleware — drop whitenoise in tests
# ----------------------------------------------------------------------
# Whitenoise warns at startup if STATIC_ROOT doesn't exist on disk. In
# tests we don't run collectstatic, so the directory legitimately isn't
# there. Strip the middleware -- static serving isn't part of what these
# tests assert on.
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m.lower()]

# ----------------------------------------------------------------------
# Core
# ----------------------------------------------------------------------
DEBUG = False
SECRET_KEY = "test-insecure-key-never-use-in-prod"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# ----------------------------------------------------------------------
# Database — in-memory SQLite per pytest-django's suite-local DB
# ----------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}


# ----------------------------------------------------------------------
# Disable migrations in tests — creates tables from models directly.
# ~3-5x faster startup for the test suite.
# ----------------------------------------------------------------------
class _DisableMigrations:
    def __contains__(self, item: str) -> bool:
        return True

    def __getitem__(self, item: str) -> None:
        return None


MIGRATION_MODULES = _DisableMigrations()

# ----------------------------------------------------------------------
# Fastest password hasher (MD5 is fine — no real passwords in tests)
# ----------------------------------------------------------------------
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# ----------------------------------------------------------------------
# Email — in-memory backend so tests can assert on mail.outbox
# ----------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# ----------------------------------------------------------------------
# Cache — local memory, isolated per test run
# ----------------------------------------------------------------------
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
}

# Deterministic, ephemeral storage for tests. InMemoryStorage (Django
# 4.2+) keeps uploaded files in process memory only -- no MEDIA_ROOT
# pollution between runs, no per-test cleanup boilerplate.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# ----------------------------------------------------------------------
# RQ -- run jobs synchronously in the test process. ASYNC=False makes
# enqueue() execute the function immediately and return a finished Job,
# so tests can assert on the Render state change without standing up a
# real worker + Redis.
# ----------------------------------------------------------------------
for _q in RQ_QUEUES.values():  # noqa: F405 — RQ_QUEUES comes from base via *
    _q["ASYNC"] = False
