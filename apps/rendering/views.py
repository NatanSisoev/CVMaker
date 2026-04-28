"""
Render views.

Phase 3.1 ships placeholders that respond with 501 Not Implemented so
URL reversal works in tests. Phase 3.4 fills these in:

  - ``enqueue_render_view``: POST -> create a Render row, dispatch the RQ
    job (or short-circuit on cache hit), return 202 + polling URL.
  - ``render_status_view``: GET -> render an HTMX fragment showing
    "queued/running/done/failed" plus the download link when done.
  - ``render_pdf_view``: GET -> stream the rendered PDF from the
    configured storage backend (S3/MinIO in prod, local FS in dev).
"""

from __future__ import annotations

from django.http import HttpResponse


def enqueue_render_view(request, cv_id):
    return HttpResponse("Not implemented yet (Phase 3.4).", status=501)


def render_status_view(request, render_id):
    return HttpResponse("Not implemented yet (Phase 3.4).", status=501)


def render_pdf_view(request, render_id):
    return HttpResponse("Not implemented yet (Phase 3.4).", status=501)
