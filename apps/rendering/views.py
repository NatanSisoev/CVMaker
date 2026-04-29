"""
Render views.

Three endpoints:

  - ``POST /cv/<cv_id>/render/`` (``rendering:enqueue``) -- create or
    cache-hit a Render. On a cache hit, redirect straight to the PDF.
    On a cache miss, return the polling fragment with a 202 status.
  - ``GET /render/<render_id>/`` (``rendering:status``) -- the polling
    fragment. HTMX self-polls every 500ms until the render is in a
    terminal state, at which point the fragment swaps to either a
    download link (done) or an error message (failed).
  - ``GET /render/<render_id>/pdf/`` (``rendering:pdf``) -- stream the
    PDF. Uses ``FileResponse`` which Django turns into a sendfile-style
    response when the WSGI server supports it.

Authorization rule: a user may only see Renders for CVs they own.
``requested_by`` differing from ``cv.user`` is allowed in principle
(shared CVs in a future phase) but isn't actually permitted today --
``cv.user == request.user`` gates all three views.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from cv.models import CV

from .models import Render, RenderStatus
from .services import enqueue_render


# ---------------------------------------------------------------------------
# POST -> enqueue (or cache-hit)
# ---------------------------------------------------------------------------
@login_required
@require_POST
def enqueue_render_view(request, cv_id):
    cv = get_object_or_404(CV, pk=cv_id, user=request.user)

    language = request.POST.get("language", "").strip()
    style = request.POST.get("style", "").strip()

    render_row = enqueue_render(
        cv,
        language=language,
        style=style,
        requested_by=request.user,
    )

    # Cache hit -- the PDF already exists. Redirect straight to it; no
    # polling round-trip required.
    if render_row.status == RenderStatus.DONE and render_row.pdf_file:
        return redirect("rendering:pdf", render_id=render_row.id)

    # Cache miss -- return the polling fragment with 202 Accepted.
    response = render(
        request,
        "rendering/_status.html",
        {"render": render_row},
    )
    response.status_code = 202
    return response


# ---------------------------------------------------------------------------
# GET -> polling fragment
# ---------------------------------------------------------------------------
@login_required
@require_GET
def render_status_view(request, render_id):
    render_row = _get_owned_render(request.user, render_id)
    return render(request, "rendering/_status.html", {"render": render_row})


# ---------------------------------------------------------------------------
# GET -> stream the PDF
# ---------------------------------------------------------------------------
@login_required
@require_GET
def render_pdf_view(request, render_id):
    render_row = _get_owned_render(request.user, render_id)

    if render_row.status != RenderStatus.DONE or not render_row.pdf_file:
        # The user navigated to the PDF URL before the render finished
        # (or after a failure). 404 keeps the surface small; the polling
        # fragment is the proper place to surface in-flight states.
        raise Http404("PDF not ready")

    response = FileResponse(
        render_row.pdf_file.open("rb"),
        content_type="application/pdf",
        as_attachment=False,
        filename=f"{render_row.cv.alias or 'cv'}.pdf",
    )
    return response


# ---------------------------------------------------------------------------
# Internal: owned-render lookup
# ---------------------------------------------------------------------------
def _get_owned_render(user, render_id) -> Render:
    """Fetch a Render the user actually owns (via cv.user), 404 otherwise.

    Centralized so the auth check has one definition. ``Render``'s
    indirection through ``cv`` means a naive
    ``Render.objects.get(pk=…)`` would let any logged-in user
    enumerate render ids -- the explicit ``cv__user`` filter prevents
    that.
    """
    try:
        return Render.objects.select_related("cv").get(pk=render_id, cv__user=user)
    except Render.DoesNotExist as exc:
        raise Http404("Render not found") from exc
