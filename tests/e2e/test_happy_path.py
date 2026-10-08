"""Phase 4 DoD: signup -> build a CV -> edit in the editor -> render -> download.

Runs a real Chromium against ``live_server``, so it exercises the bundled
HTMX + Alpine + Sortable code that the HTML-level tests can't. The render
job is executed inline (no Redis/worker needed) by patching the RQ dispatch.

Needs ``npm run build`` (static/dist/app.js) and Playwright's Chromium;
skipped otherwise.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]

# Playwright's sync API runs an event loop in this thread; Django refuses ORM
# calls from such a context unless told it's fine (the ORM isn't really async).
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

_BUNDLE = Path(__file__).resolve().parents[2] / "static" / "dist" / "app.js"
if not _BUNDLE.exists():
    pytest.skip("static/dist/app.js missing -- run `npm run build`", allow_module_level=True)

EMAIL = "ada@example.com"
PASSWORD = "Analytical-Engine-1843"


@pytest.fixture
def inline_renders(monkeypatch):
    """Run render jobs synchronously inside the request instead of via Redis."""
    from rendering import services, tasks

    monkeypatch.setattr(services, "_dispatch_render_job", lambda render: tasks.render_cv(render.id))


@pytest.fixture
def app(live_server, page, inline_renders):
    page.set_default_timeout(15_000)

    def go(path: str):
        page.goto(live_server.url + path)

    return go


def test_signup_build_edit_render_download(app, page, live_server):
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))

    # --- signup + login ---------------------------------------------------
    app("/accounts/signup/")
    page.fill("input[name=email]", EMAIL)
    page.fill("input[name=password1]", PASSWORD)
    page.fill("input[name=password2]", PASSWORD)
    page.click("form button[type=submit]")
    page.wait_for_url(re.compile(r"/accounts/login/"))

    page.fill("input[name=username]", EMAIL)
    page.fill("input[name=password]", PASSWORD)
    page.click("form button[type=submit]")
    page.wait_for_url(live_server.url + "/")

    # --- personal info ----------------------------------------------------
    app("/cv/info/create/")
    page.fill("input[name=name]", "Ada Lovelace")
    page.fill("input[name=email]", EMAIL)
    page.click("form.cv-form button[type=submit]")

    # --- an entry and a section holding it --------------------------------
    app("/entry/create/?entry_type=bullet")
    page.fill("input[name=alias]", "first-program")
    page.fill("[name=bullet]", "Wrote the first published algorithm")
    page.click("form.cv-form button[type=submit]")

    app("/section/create/")
    page.fill("input[name=title]", "Highlights")
    page.fill("input[name=alias]", "highlights")
    page.check("text=first-program")
    page.click("form.cv-form button[type=submit]")

    # --- the CV itself (Sortable-driven section order) --------------------
    app("/cv/create/")
    page.fill("input[name=alias]", "main-cv")
    page.select_option("select[name=info]", index=1)
    page.check("#section-sortable input[name=section_ids]")
    assert page.input_value("#section-order") != ""  # JS filled the hidden order
    page.click("form.cv-form button[type=submit]")
    page.wait_for_url(re.compile(r"/cv/[0-9a-f-]+/$"))

    # --- editor: open via the command palette -----------------------------
    page.keyboard.press("Control+k")
    page.fill("input[role=combobox]", "main")
    page.wait_for_selector("[role=option][aria-selected=true]:has-text('main-cv')")
    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"/editor/$"))

    # Inline accordion edit with a toast on save.
    page.click("text=first-program")
    page.fill("[id^=inline-entry-] [name=bullet]", "Published the first algorithm")
    page.click("[id^=inline-entry-] button[type=submit]")
    page.wait_for_selector("text=Saved first-program.")

    # Language chip present for the canonical language.
    assert (
        page.locator(
            "button[title$='entries translated'], button[title$='entry translated']"
        ).count()
        >= 1
    )

    # --- render preview ---------------------------------------------------
    page.click("text=Render preview")
    frame = page.wait_for_selector("#preview iframe")
    pdf_url = frame.get_attribute("src").split("#", 1)[0]

    # --- download ---------------------------------------------------------
    response = page.request.get(live_server.url + pdf_url)
    assert response.ok
    assert response.headers["content-type"] == "application/pdf"
    assert response.body()[:4] == b"%PDF"

    assert errors == [], f"JavaScript errors: {errors}"
