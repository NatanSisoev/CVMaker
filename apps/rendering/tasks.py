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

from core.rendercv import format_validation_errors
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
        render = Render.objects.select_related("cv", "cv__locale", "requested_by").get(pk=render_id)
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
        _notify(render)
        return
    except _timeout_exceptions() as exc:
        # RQ's queue timeout (35s) fired while Typst was compiling.
        logger.warning("render_cv: Render %s timed out: %s", render_id, exc)
        render.status = RenderStatus.FAILED
        render.error = (
            f"Rendering took longer than {TYPST_TIMEOUT_SECONDS} seconds and was stopped. "
            "Try a shorter CV or a simpler style, then retry."
        )
        render.completed_at = timezone.now()
        render.save(update_fields=["status", "error", "completed_at"])
        _notify(render)
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
        _notify(render)
        # Re-raise so RQ records the failure for ops dashboards.
        raise

    # Success: write the bytes through the configured storage backend
    # (FileSystemStorage in dev, S3/MinIO in prod -- see Phase 3.5).
    filename = f"{render.cv.alias or 'cv'}-{render.language or 'default'}.pdf"
    render.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
    render.status = RenderStatus.DONE
    render.completed_at = timezone.now()
    render.save(update_fields=["pdf_file", "status", "completed_at"])
    _notify(render)
    logger.info("render_cv: Render %s done in %s", render_id, render.completed_at)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _timeout_exceptions() -> tuple[type[BaseException], ...]:
    """RQ's timeout exception, resolved lazily so tests need no Redis."""
    from rq.timeouts import JobTimeoutException

    return (JobTimeoutException,)


def _notify(render) -> None:
    """Email the requester if they opted in (Settings). Never fails a render."""
    user = render.requested_by
    if user is None or not user.notify_on_render or not user.email:
        return
    from django.conf import settings
    from django.urls import reverse

    from core.email import send_templated_email

    try:
        send_templated_email(
            user.email,
            "email/render_done",
            {
                "render": render,
                "pdf_url": settings.SITE_URL
                + reverse("rendering:pdf", kwargs={"render_id": render.pk}),
                "editor_url": settings.SITE_URL + reverse("cv-editor", args=[render.cv_id]),
            },
        )
    except Exception:  # email trouble must not turn a finished render into a failed job
        logger.exception("render_cv: could not send notification for Render %s", render.pk)


class _RenderError(RuntimeError):
    """Raised by ``_render_payload_to_pdf`` for user-readable failures.

    The message gets stored verbatim in ``Render.error`` and shown in
    the UI, so phrase it for the end user.
    """


def _to_rendercv_2x(payload: dict, style: str = "") -> dict:
    """Adapt our payload to rendercv 2.x's top-level keys.

    rendercv 1.x called the settings block ``rendercv_settings``; 2.x calls it
    ``settings``. Blocks that are None (CV without design/locale/settings) are
    dropped so rendercv falls back to its defaults. ``style`` overrides the
    design theme for this render without touching the stored CVDesign.
    """
    data = {k: v for k, v in payload.items() if v is not None}
    if "rendercv_settings" in data:
        data.setdefault("settings", data.pop("rendercv_settings"))
    if style:
        data["design"] = {**data.get("design", {}), "theme": style}
    return data


def _render_payload_to_pdf(payload: dict, style: str = "", fmt: str = "pdf") -> bytes:
    """Hand a render payload to rendercv 2.x, return PDF bytes (``fmt="png"``: page 1 as PNG).

    rendercv 2.x is file-oriented, so the payload is written as YAML into a
    scratch directory that is deleted afterwards. Only Typst + PDF are
    generated. Typst compiles in-process (``typst-py``); the hard time cap is
    the RQ queue timeout (35s), which kills the work-horse if compilation
    stalls.
    """
    import pathlib
    import tempfile

    import jinja2
    import yaml
    from rendercv.exception import RenderCVUserError, RenderCVUserValidationError
    from rendercv.renderer.pdf_png import generate_pdf, generate_png
    from rendercv.renderer.typst import generate_typst
    from rendercv.schema.rendercv_model_builder import build_rendercv_dictionary_and_model

    data = _to_rendercv_2x(payload, style)
    if not data.get("cv"):
        raise _RenderError("This CV has no personal information yet. Add some and try again.")

    with tempfile.TemporaryDirectory(prefix="cvmaker-render-") as tmp:
        scratch = pathlib.Path(tmp)
        input_path = scratch / "cv.yaml"
        main_yaml = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        input_path.write_text(main_yaml, encoding="utf-8")
        try:
            _, model = build_rendercv_dictionary_and_model(
                main_yaml,
                input_file_path=input_path,
                output_folder=scratch,
                pdf_path=scratch / "cv.pdf",
                typst_path=scratch / "cv.typ",
                dont_generate_png=fmt != "png",
                dont_generate_html=True,
                dont_generate_markdown=True,
            )
            typst_path = generate_typst(model)
            if fmt == "png":
                pngs = generate_png(model, typst_path)
                if not pngs:
                    raise _RenderError("Typst finished without producing an image.")
                return pathlib.Path(pngs[0]).read_bytes()
            pdf_path = generate_pdf(model, typst_path)
        except RenderCVUserValidationError as exc:
            raise _RenderError(
                format_validation_errors(exc, "The CV data is not valid for rendering:")
            ) from exc
        except RenderCVUserError as exc:
            raise _RenderError(exc.message or "rendercv rejected this CV.") from exc
        except jinja2.TemplateSyntaxError as exc:
            raise _RenderError(f"The theme template is broken: {exc}") from exc
        if pdf_path is None or not pathlib.Path(pdf_path).exists():
            raise _RenderError("Typst finished without producing a PDF.")
        return pathlib.Path(pdf_path).read_bytes()
