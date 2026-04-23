"""
Test settings.

SQLite in-memory for speed, migrations disabled for speed, password hasher
replaced with the cheapest option for speed. These settings exist solely to
make pytest runs fast and hermetic.
"""
from __future__ import annotations

from .base import *  # noqa: F401,F403

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
# ~3–5x faster startup for the test suite.
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

# Deterministic static storage for tests
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
