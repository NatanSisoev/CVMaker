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


def test_readyz_skips_redis_when_queues_are_synchronous(client):
    assert client.get(reverse("readyz")).json()["redis"] == "skipped"


def test_readyz_503_when_redis_is_down(client, settings, monkeypatch):
    settings.RQ_QUEUES = {k: {**q, "ASYNC": True} for k, q in settings.RQ_QUEUES.items()}

    def boom(*a, **k):
        raise ConnectionError("redis down")

    monkeypatch.setattr("django_rq.get_connection", boom)
    resp = client.get(reverse("readyz"))
    assert resp.status_code == 503 and resp.json()["redis"] == "down"


def test_readyz_skips_storage_when_not_s3(client):
    assert client.get(reverse("readyz")).json()["storage"] == "skipped"


def test_readyz_checks_s3_bucket(client, monkeypatch):
    from django.core.files.storage import default_storage

    class FakeClient:
        def __init__(self, fail):
            self.fail = fail

        def head_bucket(self, Bucket):
            if self.fail:
                raise ConnectionError("s3 down")

    class FakeConn:
        def __init__(self, fail):
            self.meta = type("M", (), {"client": FakeClient(fail)})()

    monkeypatch.setattr(default_storage._wrapped, "bucket_name", "b", raising=False)
    monkeypatch.setattr(default_storage._wrapped, "connection", FakeConn(False), raising=False)
    assert client.get(reverse("readyz")).json()["storage"] == "up"
    monkeypatch.setattr(default_storage._wrapped, "connection", FakeConn(True), raising=False)
    resp = client.get(reverse("readyz"))
    assert resp.status_code == 503 and resp.json()["storage"] == "down"
