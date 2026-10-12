"""Templates gallery and style-aware quick start."""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.urls import reverse

from cv.models import CV

pytestmark = pytest.mark.django_db


def test_gallery_is_public_and_lists_every_style(client):
    body = client.get(reverse("templates")).content.decode()
    for theme in ("classic", "sb2nov", "moderncv"):
        assert reverse("template-sample", args=[theme]) in body
    assert "custom" not in body.lower().replace("customize", "")


def test_unknown_style_is_404(client):
    assert client.get("/templates/nope/sample.pdf").status_code == 404


def test_sample_pdf_renders_and_is_cached(client):
    cache.clear()
    resp = client.get(reverse("template-sample", args=["classic"]))
    assert resp.status_code == 200 and resp.content.startswith(b"%PDF")
    assert cache.get("gallery-sample-classic") == resp.content


def test_use_this_style_prefills_and_applies_the_theme(client, user):
    client.force_login(user)
    form = client.get(reverse("cv-new") + "?style=moderncv").context["form"]
    assert form["style"].value() == "moderncv"
    resp = client.post(reverse("cv-new"), {"alias": "Fancy", "style": "moderncv"})
    assert resp.status_code == 302
    assert CV.objects.get(alias="Fancy").design.theme == "moderncv"
