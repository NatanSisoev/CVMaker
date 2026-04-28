"""
Render-pipeline domain services.

Two responsibilities:

  1. **Hash derivation** -- ``compute_payload_hash(payload, style)`` walks
     the render payload + style into a canonical JSON string, then
     SHA-256s it. Same inputs, byte-identical output, every time. The
     hash *is* the cache key.

  2. **Enqueue / fetch** -- ``enqueue_render(cv, language, style)``
     short-circuits to the cached Render if a matching ``done`` row
     exists; otherwise creates a fresh ``queued`` row and (Phase 3.3)
     dispatches the RQ job. ``fetch_render(render_id)`` is the polling
     accessor.

Phase 3.3 wires the worker side; Phase 3.4 wires the views. Today the
service writes the Render row but doesn't actually start a worker --
``Render.status`` stays ``queued`` until then.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from cv.services import build_render_payload

from .models import Render, RenderStatus

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

    from cv.models import CV


# ---------------------------------------------------------------------------
# Hash derivation
# ---------------------------------------------------------------------------
def compute_payload_hash(
    payload: dict[str, Any],
    style: str = "",
    language: str = "",
) -> str:
    """SHA-256 over a canonicalized representation of (payload, style, language).

    Canonicalization rules:

      - JSON encoding with ``sort_keys=True`` so dict ordering doesn't
        affect the hash.
      - ``separators=(",", ":")`` so whitespace doesn't either.
      - ``default=str`` so dates / UUIDs / Path objects cast to strings
        instead of raising. Two payloads with the same logical content
        but different Python types (e.g., a ``datetime.date`` vs its
        isoformat string) hash to the same value.
      - ``ensure_ascii=True`` so the byte representation is platform-
        independent (no UTF-8 vs UTF-16 surprises in a worker on a
        different OS).

    ``style`` and ``language`` are appended verbatim. They participate
    in the hash *directly* (not just transitively via the payload)
    because the payload may not always reflect them -- a CV without an
    attached CVLocale produces an identical payload regardless of which
    language was requested, but the resulting PDF still must differ.
    Including them as first-class inputs prevents that cache collision.

    Empty strings are allowed and *do* participate ("no style" hashes
    differently from style="default"). This is intentional -- different
    requested intents get different cache entries even when their
    rendered payloads happen to look the same.
    """
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
        ensure_ascii=True,
    )
    raw = f"{canonical}|style={style}|language={language}".encode()
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# Enqueue
# ---------------------------------------------------------------------------
def enqueue_render(
    cv: CV,
    language: str = "",
    style: str = "",
    requested_by: AbstractBaseUser | None = None,
) -> Render:
    """Find or create a Render for this (cv, language, style) triple.

    If a ``done`` Render with the same ``payload_hash`` already exists,
    return it -- the caller can stream its ``pdf_file`` immediately, no
    worker round-trip. Otherwise create a fresh ``queued`` Render and
    (Phase 3.3) dispatch the RQ job.

    Parameters
    ----------
    cv : CV
        The CV to render.
    language : str, default ""
        Optional ISO 639-1 code override. Empty string means "use the
        CV's CVLocale.language".
    style : str, default ""
        Optional theme override. Empty string means "use the CV's
        CVDesign".
    requested_by : User, optional
        The user issuing the request, for auditing. Usually
        ``cv.user`` but kept explicit so admin/system renders can
        attribute differently.

    Returns
    -------
    Render
        Either an existing cached row (status=='done', has pdf_file) or
        a freshly created one (status=='queued', no pdf yet).
    """
    # 1. Build the payload that the worker will eventually feed to
    #    rendercv. ``build_render_payload`` is side-effect-free per
    #    Phase 2.3 -- safe to call here even if we end up cache-hitting.
    payload = build_render_payload(
        cv,
        language=language or None,
        style=style or None,
    )
    payload_hash = compute_payload_hash(payload, style=style, language=language)

    # 2. Cache lookup. Two columns in one composite-indexed query.
    cached = (
        Render.objects.filter(payload_hash=payload_hash, status=RenderStatus.DONE)
        .order_by("-completed_at")
        .first()
    )
    if cached is not None and cached.pdf_file:
        return cached

    # 3. Cache miss. Create a fresh queued row. Phase 3.3 wires
    #    ``django_rq.enqueue('rendering.tasks.render_cv', render.id)``
    #    here; until then the row sits in 'queued' until a worker (or
    #    a test fixture) progresses it.
    render = Render.objects.create(
        cv=cv,
        language=language,
        style=style,
        payload_hash=payload_hash,
        status=RenderStatus.QUEUED,
        requested_by=requested_by,
    )
    return render


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
def fetch_render(render_id) -> Render | None:
    """Polling accessor; returns ``None`` if the id doesn't exist.

    Used by the status view in Phase 3.4 -- HTMX polls every ~500ms
    until ``render.is_terminal`` flips True.
    """
    try:
        return Render.objects.get(pk=render_id)
    except Render.DoesNotExist:
        return None
