"""Shared fixtures for the Playwright end-to-end tests.

Every e2e module needs the built JS bundle (``npm run build``) and
Playwright's Chromium; the whole directory is skipped without the bundle.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Playwright's sync API runs an event loop in this thread; Django refuses ORM
# calls from such a context unless told it's fine (the ORM isn't really async).
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

_BUNDLE = Path(__file__).resolve().parents[2] / "static" / "dist" / "app.js"

PASSWORD = "Analytical-Engine-1843"


def pytest_collection_modifyitems(config, items):
    if _BUNDLE.exists():
        return
    skip = pytest.mark.skip(reason="static/dist/app.js missing -- run `npm run build`")
    for item in items:
        if "tests/e2e/" in item.nodeid.replace("\\", "/"):
            item.add_marker(skip)


@pytest.fixture
def inline_renders(monkeypatch):
    """Run render jobs synchronously inside the request instead of via Redis."""
    from rendering import services, tasks

    monkeypatch.setattr(services, "_dispatch_render_job", lambda render: tasks.render_cv(render.id))


@pytest.fixture
def js_errors(page):
    """Collects uncaught page errors; assert it's empty at the end of a test."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    return errors


@pytest.fixture
def app(live_server, page, inline_renders):
    """``app("/path/")`` navigates the Playwright page on the live server."""
    page.set_default_timeout(15_000)

    def go(path: str):
        page.goto(live_server.url + path)

    return go


@pytest.fixture
def logged_in(app, page, live_server, transactional_db):
    """A user created via the ORM and logged in through the real login form."""
    from tests.factories import UserFactory

    user = UserFactory(email="grace@example.com", username="grace")
    user.set_password(PASSWORD)
    user.save()

    app("/accounts/login/")
    page.fill("input[name=username]", user.email)
    page.fill("input[name=password]", PASSWORD)
    page.click("form button[type=submit]")
    page.wait_for_url(live_server.url + "/")
    return user
