"""Integration tests for the Phase 3.4 render views.

The views thread three concerns: authorization (only the CV owner can
see/render), HTTP status semantics (202 Accepted on enqueue, 404 on
mid-flight PDF access), and HTMX polling behavior (the fragment
self-polls while in flight and stops once terminal).
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from rendering import services as rendering_services
from rendering.models import RenderStatus
from rendering.services import enqueue_render
from tests.factories import CVFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_dispatch(monkeypatch):
    """Same stub used by the unit tests -- keep enqueue from sync-running
    the not-yet-wired _render_payload_to_pdf."""
    monkeypatch.setattr(rendering_services, "_dispatch_render_job", lambda render: None)


# ---------------------------------------------------------------------------
# POST /cv/<id>/render/  (rendering:enqueue)
# ---------------------------------------------------------------------------
class TestEnqueueView:
    def test_anon_redirected_to_login(self, client):
        cv = CVFactory()
        url = reverse("rendering:enqueue", kwargs={"cv_id": cv.pk})
        resp = client.post(url)
        assert resp.status_code in (302, 401)

    def test_owner_gets_202_on_cache_miss(self, client):
        cv = CVFactory()
        client.force_login(cv.user)
        url = reverse("rendering:enqueue", kwargs={"cv_id": cv.pk})
        resp = client.post(url)
        assert resp.status_code == 202
        # The fragment should include the polling endpoint URL.
        assert b"hx-get=" in resp.content

    def test_non_owner_gets_404(self, client):
        cv = CVFactory()
        intruder = UserFactory()
        client.force_login(intruder)
        url = reverse("rendering:enqueue", kwargs={"cv_id": cv.pk})
        resp = client.post(url)
        assert resp.status_code == 404

    def test_cache_hit_redirects_to_pdf(self, client):
        cv = CVFactory()
        # Pre-create a done Render with a stamped pdf_file name.
        first = enqueue_render(cv)
        first.status = RenderStatus.DONE
        first.pdf_file = "renders/2026/04/cached.pdf"
        first.save()

        client.force_login(cv.user)
        url = reverse("rendering:enqueue", kwargs={"cv_id": cv.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        assert reverse("rendering:pdf", kwargs={"render_id": first.id}) in resp["Location"]


# ---------------------------------------------------------------------------
# GET /render/<id>/  (rendering:status)
# ---------------------------------------------------------------------------
class TestStatusView:
    def test_owner_gets_polling_fragment(self, client):
        cv = CVFactory()
        render = enqueue_render(cv)
        client.force_login(cv.user)

        url = reverse("rendering:status", kwargs={"render_id": render.id})
        resp = client.get(url)
        assert resp.status_code == 200
        # Fragment should include hx-trigger so HTMX continues polling.
        assert b"hx-trigger=" in resp.content

    def test_non_owner_gets_404(self, client):
        cv = CVFactory()
        render = enqueue_render(cv)
        intruder = UserFactory()
        client.force_login(intruder)

        url = reverse("rendering:status", kwargs={"render_id": render.id})
        resp = client.get(url)
        assert resp.status_code == 404

    def test_terminal_done_fragment_drops_hx_trigger(self, client):
        """Once the render is done, the fragment shouldn't keep polling.

        The template gates ``hx-trigger`` on ``not render.is_terminal``.
        """
        cv = CVFactory()
        render = enqueue_render(cv)
        render.status = RenderStatus.DONE
        render.pdf_file = "renders/2026/04/cached.pdf"
        render.save()

        client.force_login(cv.user)
        url = reverse("rendering:status", kwargs={"render_id": render.id})
        resp = client.get(url)
        assert resp.status_code == 200
        assert b"hx-trigger=" not in resp.content
        # And it should expose the download link.
        assert reverse("rendering:pdf", kwargs={"render_id": render.id}).encode() in resp.content

    def test_terminal_failed_fragment_shows_error_and_retry(self, client):
        cv = CVFactory()
        render = enqueue_render(cv)
        render.status = RenderStatus.FAILED
        # Phrase the error without apostrophes -- Django auto-escapes
        # single quotes to &#x27; in template output, so the literal
        # byte string wouldn't survive verbatim.
        render.error = "Template foo was not found."
        render.save()

        client.force_login(cv.user)
        url = reverse("rendering:status", kwargs={"render_id": render.id})
        resp = client.get(url)
        assert resp.status_code == 200
        assert b"Template foo was not found" in resp.content
        assert b"Retry" in resp.content


# ---------------------------------------------------------------------------
# GET /render/<id>/pdf/  (rendering:pdf)
# ---------------------------------------------------------------------------
class TestPdfView:
    def test_404_when_not_done(self, client):
        cv = CVFactory()
        render = enqueue_render(cv)  # status == queued
        client.force_login(cv.user)

        url = reverse("rendering:pdf", kwargs={"render_id": render.id})
        resp = client.get(url)
        assert resp.status_code == 404

    def test_404_for_non_owner(self, client):
        cv = CVFactory()
        render = enqueue_render(cv)
        render.status = RenderStatus.DONE
        render.pdf_file = "renders/2026/04/x.pdf"
        render.save()

        intruder = UserFactory()
        client.force_login(intruder)
        url = reverse("rendering:pdf", kwargs={"render_id": render.id})
        resp = client.get(url)
        assert resp.status_code == 404

    def test_streams_pdf_when_done(self, client):
        from django.core.files.base import ContentFile

        cv = CVFactory()
        render = enqueue_render(cv)
        render.status = RenderStatus.DONE
        # Actually write bytes through InMemoryStorage so FileResponse
        # has something to stream.
        render.pdf_file.save("test.pdf", ContentFile(b"%PDF-1.4 fake"), save=False)
        render.save()

        client.force_login(cv.user)
        url = reverse("rendering:pdf", kwargs={"render_id": render.id})
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp["Content-Type"] == "application/pdf"
        # FileResponse iterates the file in chunks.
        body = b"".join(resp.streaming_content)
        assert body == b"%PDF-1.4 fake"
