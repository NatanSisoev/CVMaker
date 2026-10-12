"""Liveness and readiness probes."""

from __future__ import annotations

import pytest
from django.db import connection
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_healthz_is_public_and_ok(client):
    resp = client.get(reverse("healthz"))
    assert resp.status_code == 200 and resp.json() == {"status": "ok"}


def test_readyz_reports_database_up(client):
    resp = client.get(reverse("readyz"))
    assert resp.status_code == 200 and resp.json()["database"] == "up"


def test_readyz_503_when_database_is_down(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(connection, "cursor", boom)
    assert client.get(reverse("readyz")).status_code == 503


def test_probes_reject_post(client):
    assert client.post(reverse("healthz")).status_code == 405
