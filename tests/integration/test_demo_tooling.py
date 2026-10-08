"""Local-demo tooling: RENDER_INLINE dispatch and the seed_demo command."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings

from cv.models import CV
from cv.services import build_render_payload
from entries.models import BaseEntry
from rendering import tasks
from rendering.models import RenderStatus
from rendering.services import enqueue_render
from tests.factories import CVFactory

pytestmark = pytest.mark.django_db
User = get_user_model()


@override_settings(RENDER_INLINE=True)
def test_inline_dispatch_runs_the_job_without_redis(monkeypatch):
    monkeypatch.setattr(
        tasks, "_render_payload_to_pdf", lambda payload, style="": b"%PDF-1.4 inline"
    )
    render = enqueue_render(CVFactory())  # would need Redis if it went to the queue
    render.refresh_from_db()
    assert render.status == RenderStatus.DONE


@override_settings(RENDER_INLINE=False)
def test_queue_dispatch_is_used_otherwise(monkeypatch):
    import django_rq

    queued = []

    class FakeQueue:
        def enqueue(self, *args):
            queued.append(args)

    monkeypatch.setattr(django_rq, "get_queue", lambda name: FakeQueue())
    render = enqueue_render(CVFactory())
    assert queued == [("rendering.tasks.render_cv", render.id)]
    render.refresh_from_db()
    assert render.status == RenderStatus.QUEUED


def test_prod_refuses_inline_rendering(monkeypatch):
    import importlib

    monkeypatch.setenv("RENDER_INLINE", "true")
    monkeypatch.setenv("DJANGO_SECRET_KEY", "x")
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "example.com")
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "bucket")
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    import cvmaker.settings.base as base

    importlib.reload(base)
    try:
        with pytest.raises(RuntimeError, match="RENDER_INLINE"):
            importlib.import_module("cvmaker.settings.prod")
    finally:
        monkeypatch.undo()
        importlib.reload(base)


def test_seed_demo_builds_a_translated_renderable_cv_and_is_idempotent(capsys):
    call_command("seed_demo")
    call_command("seed_demo")  # second run resets instead of duplicating

    assert User.objects.filter(email="demo@cvmaker.test").count() == 1
    (cv,) = CV.objects.all()
    assert cv.sections.count() == 4
    assert BaseEntry.objects.count() == 7  # 6 in sections + 1 deliberately unused

    from cv.services import language_status

    status = {s["code"]: s["done"] for s in language_status(cv)}
    assert (
        status["en"] == 6 and 0 < status["es"] < 6 and status["fr"] == 0
    )  # FR is started but incomplete

    payload = build_render_payload(cv, language="es")
    assert payload["cv"]["sections"]["Publications"][0]["title"].startswith("Notas sobre")
    assert tasks._render_payload_to_pdf(payload, style="moderncv").startswith(b"%PDF")

    out = capsys.readouterr().out
    assert "demo@cvmaker.test" in out and "demo-password-123" in out
