"""Unit tests for the rendering pipeline (Phase 3).

These pin the cache-key contract -- if hash determinism breaks, the
cache silently bypasses, every render re-runs Typst, and we burn CPU
quietly. The tests must be loud.
"""

from __future__ import annotations

import pytest

from rendering import services as rendering_services
from rendering import tasks as rendering_tasks
from rendering.models import RenderStatus
from rendering.services import compute_payload_hash, enqueue_render, fetch_render
from rendering.tasks import render_cv
from tests.factories import CVFactory, UserFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _no_dispatch(monkeypatch):
    """Stub the RQ dispatch so enqueue tests don't synchronously run the
    task -- the stub _render_payload_to_pdf raises until the real
    rendercv 2.x integration lands. Tests that explicitly want to
    exercise render_cv invoke it directly.
    """
    monkeypatch.setattr(rendering_services, "_dispatch_render_job", lambda render: None)


# ---------------------------------------------------------------------------
# compute_payload_hash -- determinism + sensitivity
# ---------------------------------------------------------------------------
class TestComputePayloadHash:
    def test_identical_inputs_produce_identical_hash(self):
        payload = {"cv": {"name": "Alice"}, "design": {"theme": "classic"}}
        h1 = compute_payload_hash(payload, style="")
        h2 = compute_payload_hash(payload, style="")
        assert h1 == h2

    def test_dict_ordering_does_not_affect_hash(self):
        """JSON canonicalization should produce the same hash regardless
        of dict insertion order."""
        a = {"a": 1, "b": 2, "c": 3}
        b = {"c": 3, "a": 1, "b": 2}
        assert compute_payload_hash(a) == compute_payload_hash(b)

    def test_nested_dict_ordering_does_not_affect_hash(self):
        a = {"outer": {"a": 1, "b": 2}}
        b = {"outer": {"b": 2, "a": 1}}
        assert compute_payload_hash(a) == compute_payload_hash(b)

    def test_different_payload_produces_different_hash(self):
        a = compute_payload_hash({"name": "Alice"})
        b = compute_payload_hash({"name": "Bob"})
        assert a != b

    def test_style_participates_in_hash(self):
        """Two payloads identical except for style should not collide."""
        payload = {"name": "Alice"}
        a = compute_payload_hash(payload, style="classic")
        b = compute_payload_hash(payload, style="moderncv")
        assert a != b

    def test_empty_style_is_distinct_from_named_style(self):
        payload = {"name": "Alice"}
        a = compute_payload_hash(payload, style="")
        b = compute_payload_hash(payload, style="default")
        assert a != b

    def test_language_participates_in_hash(self):
        """Critical property -- the payload may not reflect the
        requested language (a CV without a CVLocale produces the same
        payload regardless), so language must be a first-class input."""
        payload = {"name": "Alice"}
        en = compute_payload_hash(payload, language="en")
        es = compute_payload_hash(payload, language="es")
        assert en != es

    def test_empty_language_distinct_from_named(self):
        payload = {"name": "Alice"}
        unspecified = compute_payload_hash(payload, language="")
        en = compute_payload_hash(payload, language="en")
        assert unspecified != en

    def test_hash_is_64_hex_chars(self):
        """Sanity check: SHA-256 -> 64 hex chars."""
        h = compute_payload_hash({"x": 1})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_handles_non_json_native_values(self):
        """Dates, UUIDs, Paths -- ``default=str`` should cast cleanly."""
        import datetime as dt
        import uuid

        payload = {
            "date": dt.date(2024, 1, 1),
            "id": uuid.UUID("12345678-1234-5678-1234-567812345678"),
        }
        # Should not raise -- the hash is just a string.
        h = compute_payload_hash(payload)
        assert isinstance(h, str)


# ---------------------------------------------------------------------------
# enqueue_render -- create + cache hit
# ---------------------------------------------------------------------------
class TestEnqueueRender:
    def test_first_call_creates_queued_render(self):
        cv = CVFactory()
        render = enqueue_render(cv, requested_by=cv.user)
        assert render.cv_id == cv.pk
        assert render.status == RenderStatus.QUEUED
        assert render.payload_hash  # 64-char SHA-256
        assert len(render.payload_hash) == 64

    def test_records_requesting_user(self):
        cv = CVFactory()
        user = UserFactory()
        render = enqueue_render(cv, requested_by=user)
        assert render.requested_by_id == user.pk

    def test_two_calls_with_same_inputs_create_two_queued_rows(self):
        """Cache short-circuits only on DONE -- two queued renders for
        identical input are fine; the worker dedupes via hash later."""
        cv = CVFactory()
        a = enqueue_render(cv)
        b = enqueue_render(cv)
        assert a.id != b.id
        assert a.payload_hash == b.payload_hash

    def test_done_render_short_circuits(self):
        """A DONE render with matching hash is returned, not duplicated."""
        cv = CVFactory()

        # Simulate a completed render. Stamp the FieldFile.name directly
        # so we bypass storage I/O -- the cache guard just checks that
        # ``pdf_file`` is truthy (i.e. has a non-empty name), not that
        # the underlying bytes exist on disk.
        first = enqueue_render(cv)
        first.status = RenderStatus.DONE
        first.pdf_file = "renders/2026/04/fake.pdf"
        first.save()

        # Same inputs -> should return the cached row.
        second = enqueue_render(cv)
        assert second.id == first.id
        assert second.status == RenderStatus.DONE

    def test_failed_render_does_not_short_circuit(self):
        """A FAILED render with matching hash should not be returned --
        we want the user's retry to actually retry."""
        cv = CVFactory()

        first = enqueue_render(cv)
        first.status = RenderStatus.FAILED
        first.error = "Typst exited 1"
        first.save()

        second = enqueue_render(cv)
        assert second.id != first.id
        assert second.status == RenderStatus.QUEUED

    def test_different_language_creates_separate_render(self):
        cv = CVFactory()
        en = enqueue_render(cv, language="en")
        es = enqueue_render(cv, language="es")
        assert en.id != es.id
        assert en.payload_hash != es.payload_hash


# ---------------------------------------------------------------------------
# fetch_render
# ---------------------------------------------------------------------------
class TestFetchRender:
    def test_returns_render_for_existing_id(self):
        cv = CVFactory()
        render = enqueue_render(cv)
        assert fetch_render(render.id) == render

    def test_returns_none_for_missing_id(self):
        assert fetch_render("00000000-0000-0000-0000-000000000000") is None


# ---------------------------------------------------------------------------
# Render.is_terminal property
# ---------------------------------------------------------------------------
class TestIsTerminal:
    def test_queued_is_not_terminal(self):
        cv = CVFactory()
        render = enqueue_render(cv)
        assert not render.is_terminal

    def test_done_is_terminal(self):
        cv = CVFactory()
        render = enqueue_render(cv)
        render.status = RenderStatus.DONE
        assert render.is_terminal

    def test_failed_is_terminal(self):
        cv = CVFactory()
        render = enqueue_render(cv)
        render.status = RenderStatus.FAILED
        assert render.is_terminal


# ---------------------------------------------------------------------------
# render_cv -- the worker entry point
# ---------------------------------------------------------------------------
class TestRenderCv:
    def test_writes_pdf_and_marks_done(self, monkeypatch):
        cv = CVFactory()
        render = enqueue_render(cv)

        # Stand in for the real Typst subprocess.
        monkeypatch.setattr(
            rendering_tasks,
            "_render_payload_to_pdf",
            lambda payload, style="": b"%PDF-1.4 fake from test",
        )

        render_cv(render.id)

        render.refresh_from_db()
        assert render.status == RenderStatus.DONE
        assert render.completed_at is not None
        assert render.pdf_file  # FieldFile truthy when .name is set
        assert render.error == ""

    def test_marks_failed_on_render_error_with_user_readable_message(self, monkeypatch):
        cv = CVFactory()
        render = enqueue_render(cv)

        def raise_render_error(payload, style=""):
            raise rendering_tasks._RenderError("Template 'foo' not found. Did you mean 'bar'?")

        monkeypatch.setattr(rendering_tasks, "_render_payload_to_pdf", raise_render_error)

        render_cv(render.id)

        render.refresh_from_db()
        assert render.status == RenderStatus.FAILED
        assert render.completed_at is not None
        assert "Template 'foo' not found" in render.error
        assert not render.pdf_file

    def test_unexpected_exception_stores_generic_message_and_reraises(self, monkeypatch):
        """Genuine bugs should reach RQ's failure dashboard but the
        user shouldn't see internals."""
        cv = CVFactory()
        render = enqueue_render(cv)

        def boom(payload, style=""):
            raise RuntimeError("internal bug: division by zero")

        monkeypatch.setattr(rendering_tasks, "_render_payload_to_pdf", boom)

        with pytest.raises(RuntimeError, match="division by zero"):
            render_cv(render.id)

        render.refresh_from_db()
        assert render.status == RenderStatus.FAILED
        assert "unexpected error" in render.error.lower()
        # No internal text leaked.
        assert "division by zero" not in render.error

    def test_skips_already_terminal_render(self, monkeypatch):
        cv = CVFactory()
        render = enqueue_render(cv)
        render.status = RenderStatus.DONE
        render.save()

        called = []
        monkeypatch.setattr(
            rendering_tasks,
            "_render_payload_to_pdf",
            lambda payload, style="": called.append(1) or b"x",
        )

        render_cv(render.id)
        assert called == []

    def test_missing_render_id_is_a_noop(self, monkeypatch):
        """Worker race: row was deleted between enqueue and pickup."""
        called = []
        monkeypatch.setattr(
            rendering_tasks,
            "_render_payload_to_pdf",
            lambda payload, style="": called.append(1) or b"x",
        )

        # Should not raise.
        render_cv("00000000-0000-0000-0000-000000000000")
        assert called == []
