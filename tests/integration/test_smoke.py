"""Smoke tests.

Cheap, fast checks that catch catastrophic regressions: URL reversal,
public pages returning 200, the admin loading, migrations applying cleanly.

These are the first tests CI runs — if they fail, nothing else matters.
"""

from __future__ import annotations

import pytest
from django.urls import URLPattern, URLResolver, get_resolver, reverse

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name",
    [
        "homepage",
        "about",
        "help",
        "contact",
        "status",
        "templates",
        "import",
    ],
)
def test_public_stubs_render_200(client, name):
    """Every Phase 0 placeholder route should still return a friendly page."""
    url = reverse(name)
    resp = client.get(url)
    assert resp.status_code == 200


def test_admin_login_page(client):
    resp = client.get("/admin/login/")
    assert resp.status_code == 200


def test_admin_index_redirects_when_anon(client):
    resp = client.get("/admin/")
    # Django admin redirects anonymous users to the login page.
    assert resp.status_code in (302, 301)


def test_admin_index_authed(admin_client):
    resp = admin_client.get("/admin/")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# URL reversal — every named route must reverse without raising.
# ---------------------------------------------------------------------------
def _named_patterns(patterns):
    for p in patterns:
        if isinstance(p, URLPattern) and p.name:
            yield p
        elif isinstance(p, URLResolver):
            yield from _named_patterns(p.url_patterns)


def test_every_named_url_reverses():
    """Catches typos like `cvdesgin-list` at test time, not runtime."""
    resolver = get_resolver()
    failures = []
    for pattern in _named_patterns(resolver.url_patterns):
        try:
            reverse(pattern.name)
        except Exception as exc:  # noqa: BLE001 — pytest reports all failures together
            # Some routes require URL kwargs; skip those — they're validated per-view.
            if "NoReverseMatch" in exc.__class__.__name__ and "argument" in str(exc):
                continue
            failures.append((pattern.name, str(exc)))
    assert not failures, f"Unreversible URLs: {failures}"
