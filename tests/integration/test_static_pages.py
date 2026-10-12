import pytest
from django.db import connection
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_about_and_status_are_real_pages(client):
    assert b"About CVMaker" in client.get(reverse("about")).content
    body = client.get(reverse("status")).content
    assert b"Operational" in body and b"Database" in body


def test_status_page_503_when_database_down(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(connection, "cursor", boom)
    resp = client.get(reverse("status"))
    assert resp.status_code == 503 and b"Unavailable" in resp.content


def test_robots_blocks_private_areas_and_points_at_sitemap(client):
    body = client.get("/robots.txt").content.decode()
    assert "Disallow: /cv/" in body and "Disallow: /s/" in body and "sitemap.xml" in body


def test_sitemap_lists_public_pages_and_only_published_profiles(client, user):
    from tests.factories import CVFactory, UserFactory

    published = UserFactory(public_handle="ada")
    published.public_cv = CVFactory(user=published)
    published.save()
    UserFactory(public_handle="hidden")  # handle but no CV -> not listed
    body = client.get("/sitemap.xml").content.decode()
    assert "/@ada/" in body and "/@hidden/" not in body and "/templates/" in body
