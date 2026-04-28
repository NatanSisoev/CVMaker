"""
Render -- one row per (cv, language, style) render request.

The render is the unit of caching. Identical inputs produce identical
``payload_hash`` values, so a fresh request that matches an existing
``done`` Render returns the cached PDF instantly without re-running
Typst.

Status flow::

    queued  -> running   (worker picks up the job)
    running -> done      (PDF written, completed_at set)
    running -> failed    (subprocess error, error stored, completed_at set)

The ``error`` column is plaintext from Typst/rendercv stderr -- displayed
to the user verbatim if a render fails. Phase 3.3 wires the worker;
Phase 3.4 wires the polling views.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class RenderStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"


class Render(models.Model):
    """A single CV render request -- queued, running, done, or failed."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    cv = models.ForeignKey(
        "cv.CV",
        on_delete=models.CASCADE,
        related_name="renders",
        help_text="The CV being rendered.",
    )

    # ------------------------------------------------------------------
    # Render parameters -- (language, style) is part of the cache key.
    # ------------------------------------------------------------------
    language = models.CharField(
        max_length=2,
        blank=True,
        default="",
        help_text="ISO 639-1 code; empty string means 'use the CV's CVLocale.language'.",
    )
    style = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Theme/style override; empty string means 'use the CV's CVDesign'.",
    )

    # SHA-256 of the canonical render payload + style. Two requests with
    # the same hash get the same PDF; a fresh hash re-renders.
    payload_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="SHA-256 of the canonicalized render input. Cache key.",
    )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    status = models.CharField(
        max_length=10,
        choices=RenderStatus.choices,
        default=RenderStatus.QUEUED,
        db_index=True,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    pdf_file = models.FileField(
        upload_to="renders/%Y/%m/",
        null=True,
        blank=True,
        help_text="The rendered PDF; populated when status == 'done'.",
    )
    error = models.TextField(
        blank=True,
        default="",
        help_text="Captured stderr/exception text when status == 'failed'.",
    )

    # Who requested it -- helps with auditing and per-user rate limits in
    # Phase 7. Always the CV owner today; could differ for shared CVs in
    # the future.
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="renders",
    )

    class Meta:
        # Tuples (vs lists) sidestep ruff's RUF012 -- Django reads Meta
        # at class-creation time and accepts either container.
        ordering = ("-requested_at",)
        indexes = (
            # The cache hot-path query: "is there a done Render with this hash?"
            models.Index(fields=("payload_hash", "status")),
        )

    def __str__(self) -> str:
        return f"Render({self.id}, cv={self.cv_id}, status={self.status})"

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    @property
    def is_terminal(self) -> bool:
        """True once the render has reached a final state (done or failed)."""
        return self.status in {RenderStatus.DONE, RenderStatus.FAILED}
