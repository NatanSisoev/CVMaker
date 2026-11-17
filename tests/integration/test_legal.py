"""Legal pages render from docs/legal/*.md."""

from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("slug", "heading"),
    [("terms", "Terms of Service"), ("privacy", "Privacy Policy"), ("cookies", "Cookie Policy")],
)
def test_legal_page_renders(client, slug, heading):
    resp = client.get(reverse("legal", args=[slug]))
    assert resp.status_code == 200
    assert f"<h1>{heading}</h1>" in resp.content.decode()


def test_unknown_legal_page_404(client):
    assert client.get("/legal/nope/").status_code == 404


def test_footer_links_to_legal_pages(client):
    html = client.get(reverse("about")).content.decode()
    assert reverse("legal", args=["privacy"]) in html
