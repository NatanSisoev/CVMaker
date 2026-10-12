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
