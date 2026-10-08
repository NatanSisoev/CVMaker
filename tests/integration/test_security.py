"""Phase 6 hardening: rate limits, 429 handling, security headers, PDF framing."""

from __future__ import annotations

import json

import pytest
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from rendering import services as rendering_services
from rendering.models import Render, RenderStatus
from tests.factories import CVFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_dispatch(monkeypatch):
    monkeypatch.setattr(rendering_services, "_dispatch_render_job", lambda render: None)


# ---------------------------------------------------------------------------
# Rate limits
# ---------------------------------------------------------------------------
# Login and signup limits are allauth's ACCOUNT_RATE_LIMITS now; see test_auth_flow.py.


def test_render_web_view_is_limited_per_user_with_htmx_toast(client):
    cv = CVFactory()
    client.force_login(cv.user)
    url = reverse("rendering:enqueue", kwargs={"cv_id": cv.id})
    for _ in range(30):
        assert client.post(url, HTTP_HX_REQUEST="true").status_code in (200, 202)

    resp = client.post(url, HTTP_HX_REQUEST="true")
    assert resp.status_code == 429
    assert json.loads(resp["HX-Trigger"])["toast"]["variant"] == "error"


def test_render_limit_is_per_user(client, other_user):
    mine, theirs = CVFactory(), CVFactory(user=other_user)
    client.force_login(mine.user)
    for _ in range(31):
        client.post(reverse("rendering:enqueue", kwargs={"cv_id": mine.id}))
    client.force_login(other_user)
    resp = client.post(reverse("rendering:enqueue", kwargs={"cv_id": theirs.id}))
    assert resp.status_code in (200, 202)


def test_api_render_is_throttled_with_json_429():
    cv = CVFactory()
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=cv.user).key}")
    url = reverse("api:cv-render", args=[cv.id])
    for _ in range(30):
        assert api.post(url).status_code in (200, 202)
    resp = api.post(url)
    assert resp.status_code == 429
    assert "throttled" in resp.json()["detail"].lower()
    # Reads are not throttled by the render scope.
    assert api.get(reverse("api:cv-list")).status_code == 200


def test_settings_posts_are_limited(client, user):
    client.force_login(user)
    url = reverse("profile")
    for _ in range(10):
        client.post(url, {"action": "password", "old_password": "nope"})
    assert client.post(url, {"action": "password", "old_password": "nope"}).status_code == 429


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------
def test_permissions_policy_and_framing_headers_on_pages(client):
    resp = client.get(reverse("homepage"))
    assert "camera=()" in resp["Permissions-Policy"]
    assert resp["X-Frame-Options"] == "DENY"
    assert resp["X-Content-Type-Options"] == "nosniff"
    assert resp["Referrer-Policy"] == "same-origin"


def test_pdf_can_be_framed_by_the_editor_but_not_cross_origin(client):
    cv = CVFactory()
    render = Render.objects.create(cv=cv, payload_hash="h", status=RenderStatus.DONE)
    render.pdf_file.save("x.pdf", ContentFile(b"%PDF-1.4"), save=True)
    client.force_login(cv.user)

    resp = client.get(reverse("rendering:pdf", kwargs={"render_id": render.id}))
    assert resp.status_code == 200
    assert resp["X-Frame-Options"] == "SAMEORIGIN"  # was DENY: blank editor preview


@override_settings(PERMISSIONS_POLICY="")
def test_permissions_policy_can_be_disabled(client):
    from core.middleware import PermissionsPolicyMiddleware

    mw = PermissionsPolicyMiddleware(lambda request: __import__("django").http.HttpResponse())
    assert "Permissions-Policy" not in mw(None)
