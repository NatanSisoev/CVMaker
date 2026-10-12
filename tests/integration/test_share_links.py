"""Render history and expiring share links."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from rendering.models import Render, RenderStatus, ShareLink
from tests.factories import CVFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def done_render(db):
    cv = CVFactory(alias="shared-cv")
    r = Render.objects.create(
        cv=cv, payload_hash="h", status=RenderStatus.DONE, requested_by=cv.user
    )
    r.pdf_file.save("x.pdf", ContentFile(b"%PDF-1.4 fake"))
    return r


def test_history_lists_renders_for_owner_only(client, done_render):
    url = reverse("rendering:history", args=[done_render.cv_id])
    assert client.get(url).status_code == 302
    client.force_login(UserFactory())
    assert client.get(url).status_code == 404
    client.force_login(done_render.cv.user)
    body = client.get(url).content.decode()
    assert "Render history" in body and reverse("rendering:pdf", args=[done_render.id]) in body


def test_create_share_link_then_public_download(client, done_render):
    client.force_login(done_render.cv.user)
    resp = client.post(reverse("rendering:share-create", args=[done_render.id]), {"duration": "1d"})
    assert resp.status_code == 302
    link = ShareLink.objects.get()
    assert timedelta(hours=23) < link.expires_at - timezone.now() <= timedelta(days=1)

    client.logout()  # anonymous visitor
    pub = client.get(reverse("rendering:shared", args=[link.token]))
    assert pub.status_code == 200 and b"".join(pub.streaming_content).startswith(b"%PDF")
    assert pub["X-Robots-Tag"] == "noindex, nofollow"
    link.refresh_from_db()
    assert link.view_count == 1


def test_expired_and_revoked_links_404(client, done_render):
    expired = ShareLink.objects.create(
        render=done_render, expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert client.get(reverse("rendering:shared", args=[expired.token])).status_code == 404

    live = ShareLink.objects.create(
        render=done_render, expires_at=timezone.now() + timedelta(days=1)
    )
    client.force_login(done_render.cv.user)
    client.post(reverse("rendering:share-revoke", args=[live.id]))
    client.logout()
    assert client.get(reverse("rendering:shared", args=[live.token])).status_code == 404


def test_only_owner_can_share_or_revoke(client, done_render):
    link = ShareLink.objects.create(
        render=done_render, expires_at=timezone.now() + timedelta(days=1)
    )
    client.force_login(UserFactory())
    assert client.post(reverse("rendering:share-create", args=[done_render.id])).status_code == 404
    assert client.post(reverse("rendering:share-revoke", args=[link.id])).status_code == 404
    link.refresh_from_db()
    assert not link.revoked


def test_unfinished_render_cannot_be_shared(client):
    cv = CVFactory()
    r = Render.objects.create(cv=cv, payload_hash="h", status=RenderStatus.QUEUED)
    client.force_login(cv.user)
    assert client.post(reverse("rendering:share-create", args=[r.id])).status_code == 404


def test_unknown_token_404(client):
    assert client.get(reverse("rendering:shared", args=["nope"])).status_code == 404
