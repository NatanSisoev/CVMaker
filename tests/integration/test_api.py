"""/api/v1 (Phase 5): auth, scoping, render flow, schema contract, CLI."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from cv.models import CVInfo
from rendering import services as rendering_services
from rendering import tasks
from sections.models import CVSection, SectionEntry
from tests.factories import BulletEntryFactory, CVFactory, SectionFactory

pytestmark = pytest.mark.django_db

SCHEMA_SNAPSHOT = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.yaml"


@pytest.fixture
def api(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")
    return client


@pytest.fixture
def full_cv(user):
    info = CVInfo.objects.create(user=user, alias="me", name="Ada Lovelace")
    cv = CVFactory(user=user, alias="api-cv", info=info)
    section = SectionFactory(user=user, title="Highlights")
    entry = BulletEntryFactory(
        user=user, bullet="First algorithm", translations={"es": {"bullet": "x"}}
    )
    SectionEntry.objects.create(section=section, entry=entry, order=0)
    CVSection.objects.create(cv=cv, section=section, order=0)
    return cv


@pytest.fixture
def inline_renders(monkeypatch):
    monkeypatch.setattr(rendering_services, "_dispatch_render_job", lambda r: tasks.render_cv(r.id))


# ---------------------------------------------------------------------------
# Auth + scoping
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name", ["api:cv-list", "api:section-list", "api:entry-list", "api:render-list"]
)
def test_anonymous_is_rejected(name):
    assert APIClient().get(reverse(name)).status_code in (401, 403)


def test_bad_token_is_rejected():
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token not-a-real-key")
    assert client.get(reverse("api:cv-list")).status_code == 401


def test_session_auth_works_for_the_browser(client, user, full_cv):
    client.force_login(user)
    assert client.get(reverse("api:cv-list")).status_code == 200


def test_lists_only_your_own_rows(api, full_cv, other_user):
    CVFactory(user=other_user, alias="not-mine")
    BulletEntryFactory(user=other_user, alias="theirs")

    cvs = api.get(reverse("api:cv-list")).json()["results"]
    assert [c["alias"] for c in cvs] == ["api-cv"]
    entries = api.get(reverse("api:entry-list")).json()["results"]
    assert "theirs" not in {e["alias"] for e in entries}


def test_other_users_cv_is_404(api, other_user):
    theirs = CVFactory(user=other_user)
    assert api.get(reverse("api:cv-detail", args=[theirs.id])).status_code == 404
    assert api.post(reverse("api:cv-render", args=[theirs.id])).status_code == 404


def test_read_only(api, full_cv):
    url = reverse("api:cv-detail", args=[full_cv.id])
    assert api.delete(url).status_code == 405
    assert api.patch(url, {"alias": "x"}).status_code == 405


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------
def test_cv_detail_shape(api, full_cv):
    body = api.get(reverse("api:cv-detail", args=[full_cv.id])).json()
    assert body["alias"] == "api-cv"
    assert len(body["sections"]) == 1
    assert {"code": "es", "done": 1, "total": 1} in body["languages"]


def test_entry_and_section_shapes(api, full_cv):
    (entry,) = api.get(reverse("api:entry-list")).json()["results"]
    assert entry["type"] == "bullet"
    assert entry["content"] == {"bullet": "First algorithm"}
    assert entry["translations"] == {"es": {"bullet": "x"}}

    (section,) = api.get(reverse("api:section-list")).json()["results"]
    assert section["entries"] == [entry["id"]]


# ---------------------------------------------------------------------------
# Render flow
# ---------------------------------------------------------------------------
def test_render_then_cache_hit_then_pdf(api, full_cv, inline_renders):
    url = reverse("api:cv-render", args=[full_cv.id])

    first = api.post(url, {"language": "es", "style": "moderncv"}, format="json")
    assert first.status_code == 202  # was queued (then ran inline)
    render_id = first.json()["id"]
    done = api.get(reverse("api:render-detail", args=[render_id])).json()
    assert done["status"] == "done"
    assert done["pdf_url"].endswith(f"/api/v1/renders/{render_id}/pdf/")

    again = api.post(url, {"language": "es", "style": "moderncv"}, format="json")
    assert again.status_code == 200 and again.json()["id"] == render_id  # cache hit

    pdf = api.get(reverse("api:render-pdf", args=[render_id]))
    assert pdf["Content-Type"] == "application/pdf"
    assert b"".join(pdf.streaming_content).startswith(b"%PDF")


@pytest.mark.parametrize(
    "payload", [{"language": "spanish"}, {"style": "custom"}, {"style": "nope"}]
)
def test_render_rejects_bad_parameters(api, full_cv, payload):
    resp = api.post(reverse("api:cv-render", args=[full_cv.id]), payload, format="json")
    assert resp.status_code == 400


def test_pdf_404_until_done(api, full_cv, monkeypatch):
    monkeypatch.setattr(rendering_services, "_dispatch_render_job", lambda r: None)
    render_id = api.post(reverse("api:cv-render", args=[full_cv.id])).json()["id"]
    assert api.get(reverse("api:render-pdf", args=[render_id])).status_code == 404


# ---------------------------------------------------------------------------
# Docs + schema contract
# ---------------------------------------------------------------------------
def test_docs_are_staff_only(api, admin_client):
    assert api.get(reverse("api:docs")).status_code == 403
    assert admin_client.get(reverse("api:docs")).status_code == 200


def test_schema_matches_committed_snapshot():
    """Breaking (or any) API changes must update docs/api/openapi.yaml on purpose:
    run with UPDATE_API_SCHEMA=1 to rewrite the snapshot, then review the diff."""
    from django.core.management import call_command

    out = SCHEMA_SNAPSHOT.with_suffix(".generated.yaml")
    try:
        call_command("spectacular", "--file", str(out), "--validate", "--fail-on-warn")
        generated = out.read_text(encoding="utf-8")
    finally:
        out.unlink(missing_ok=True)

    if os.environ.get("UPDATE_API_SCHEMA") == "1":
        SCHEMA_SNAPSHOT.write_text(generated, encoding="utf-8", newline="\n")
    assert generated == SCHEMA_SNAPSHOT.read_text(encoding="utf-8"), (
        "API schema changed. If intended, rerun with UPDATE_API_SCHEMA=1 and commit docs/api/openapi.yaml."
    )


# ---------------------------------------------------------------------------
# Settings page token management
# ---------------------------------------------------------------------------
def test_settings_creates_regenerates_and_revokes_token(client, user):
    client.force_login(user)
    url = reverse("profile")

    client.post(url, {"action": "token-create"})
    first = Token.objects.get(user=user).key
    assert first.encode() in client.get(url).content

    client.post(url, {"action": "token-create"})
    second = Token.objects.get(user=user).key
    assert second != first

    client.post(url, {"action": "token-revoke"})
    assert not Token.objects.filter(user=user).exists()


# ---------------------------------------------------------------------------
# The Phase 5 DoD: a ~50-line CLI lists CVs and downloads a PDF with a token
# ---------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_cli_lists_and_downloads(
    live_server, user, full_cv, inline_renders, tmp_path, monkeypatch, capsys
):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "cvmaker_cli", Path(__file__).resolve().parents[2] / "scripts" / "cvmaker_cli.py"
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    monkeypatch.setenv("CVMAKER_URL", live_server.url)
    monkeypatch.setenv("CVMAKER_TOKEN", Token.objects.create(user=user).key)

    assert cli.main(["list"]) == 0
    assert "api-cv" in capsys.readouterr().out

    out = tmp_path / "cv.pdf"
    assert cli.main(["render", str(full_cv.id), "--language", "es", "-o", str(out)]) == 0
    assert out.read_bytes().startswith(b"%PDF")
