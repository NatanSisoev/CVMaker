"""
Background tasks for the rendering pipeline.

The single entry point is ``render_cv(render_id)``, dispatched by
``rendering.services.enqueue_render`` via ``django_rq.enqueue``. The
worker (one of the ``docker compose up worker`` containers) picks up
the job, runs Typst in a hardened subprocess, writes the PDF, and flips
the Render row's status.

Sandbox model (see ADR-0007 for the full reasoning):

  - **Process isolation**: container-level. The worker container runs
    as a non-root user, has a 256 MiB memory cap, and -- crucially --
    starts with no outbound network policy in compose. Typst doesn't
    need the network at render time; rendercv has already gathered all
    inputs by the time we invoke the binary.
  - **Time bound**: ``subprocess.run(..., timeout=30)``. RQ's per-queue
    DEFAULT_TIMEOUT is 35 to leave room for orchestration overhead
    (Render row updates, file writes); if Typst itself stalls past 30s
    we kill it cleanly.
  - **Output capture**: stdout is discarded (Typst's progress chatter),
    stderr is captured and stored verbatim in ``Render.error`` on
    failure. Users see the message in the UI -- "no template named foo,
    did you mean bar?" reads better than "exit 1".

Tests mock ``_render_payload_to_pdf`` so the suite stays fast and
hermetic; the integration test (Phase 3.6) runs the real subprocess
against a known-good payload.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.core.files.base import ContentFile
from django.utils import timezone

from cv.services import build_render_payload

from .models import Render, RenderStatus

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Hard time budget for the Typst subprocess. ADR-0007 ratchets this if
# we ever ship templates that legitimately need more.
TYPST_TIMEOUT_SECONDS = 30


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def render_cv(render_id) -> None:
    """Render the PDF for the given Render row.

    Idempotent on the row: if the Render is already in a terminal state
    when the worker picks it up (e.g. a duplicate enqueue, or a retry
    after a worker crash), exits without touching anything.
    """
    try:
        render = Render.objects.select_related("cv", "cv__locale").get(pk=render_id)
    except Render.DoesNotExist:
        logger.warning("render_cv: Render %s gone before worker pickup", render_id)
        return

    if render.is_terminal:
        logger.info(
            "render_cv: Render %s already terminal (%s), skipping", render_id, render.status
        )
        return

    render.status = RenderStatus.RUNNING
    render.save(update_fields=["status"])

    try:
        payload = build_render_payload(
            render.cv,
            language=render.language or None,
            style=render.style or None,
        )
        pdf_bytes = _render_payload_to_pdf(payload, style=render.style)
    except _RenderError as exc:
        # Captured stderr or our own RenderError message. Either way it's
        # already user-readable -- store it directly.
        logger.warning("render_cv: Render %s failed: %s", render_id, exc)
        render.status = RenderStatus.FAILED
        render.error = str(exc)
        render.completed_at = timezone.now()
        render.save(update_fields=["status", "error", "completed_at"])
        return
    except Exception:  # last-resort
        # Anything that escaped the inner handler is a genuine bug --
        # log the full traceback for ops, store a generic user-facing
        # message so we don't leak internals into the UI.
        logger.exception("render_cv: Render %s crashed", render_id)
        render.status = RenderStatus.FAILED
        render.error = (
            "An unexpected error occurred while rendering. "
            "Please try again, or contact support if the problem persists."
        )
        render.completed_at = timezone.now()
        render.save(update_fields=["status", "error", "completed_at"])
        # Re-raise so RQ records the failure for ops dashboards.
        raise

    # Success: write the bytes through the configured storage backend
    # (FileSystemStorage in dev, S3/MinIO in prod -- see Phase 3.5).
    filename = f"{render.cv.alias or 'cv'}-{render.language or 'default'}.pdf"
    render.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
    render.status = RenderStatus.DONE
    render.completed_at = timezone.now()
    render.save(update_fields=["pdf_file", "status", "completed_at"])
    logger.info("render_cv: Render %s done in %s", render_id, render.completed_at)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
class _RenderError(RuntimeError):
    """Raised by ``_render_payload_to_pdf`` for user-readable failures.

    The message gets stored verbatim in ``Render.error`` and shown in
    the UI, so phrase it for the end user.
    """


def _render_payload_to_pdf(payload: dict, style: str = "") -> bytes:
    """Hand a render payload to rendercv 2.x, return PDF bytes.

    Phase 3.3 ships the orchestration; the actual rendercv invocation
    is stubbed -- the real call lands once the rendercv 2.x API surface
    is pinned (the package is in flux around the renderer module
    rename, see ``scripts/fix_rendercv_imports.py``). Tests mock this
    function entirely so they don't depend on the integration shape.
    """
    # TODO(phase-3.3-followup): replace with the real rendercv 2.x call
    #   once the API stabilizes. Sketch:
    #
    #     from rendercv.api import (
    #         create_a_typst_file_and_render_a_pdf_from_it,
    #     )
    #     pdf_path = create_a_typst_file_and_render_a_pdf_from_it(
    #         input_dictionary=payload,
    #         output_directory=<scratch dir>,
    #         timeout=TYPST_TIMEOUT_SECONDS,
    #     )
    #     return Path(pdf_path).read_bytes()
    #
    # Subprocess sandboxing: rendercv 2.x already invokes Typst via
    # subprocess.run with shell=False. Container-level limits (memory,
    # network policy, non-root user) provide the rest of the sandbox;
    # see the docker/worker.Dockerfile + compose.yaml.
    raise _RenderError(
        "Rendering is not wired to rendercv yet -- Phase 3.3 follow-up. "
        "This Render row was created and queued correctly, but the worker "
        "stub has no real PDF generator behind it."
    )
