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
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from cv.models import CV

from .models import Render, RenderStatus
from .services import enqueue_render


# ---------------------------------------------------------------------------
# POST -> enqueue (or cache-hit)
# ---------------------------------------------------------------------------
@login_required
@require_POST
@ratelimit(group="render", key="user", rate="30/m")
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

    preview = bool(request.POST.get("preview"))
    is_htmx = request.headers.get("HX-Request") == "true"
    cache_hit = render_row.status == RenderStatus.DONE and bool(render_row.pdf_file)

    # Cache hit from a plain form post -- redirect straight to the PDF.
    # (HTMX would follow the redirect and swap raw PDF bytes into the page,
    # so HTMX callers get the fragment instead.)
    if cache_hit and not is_htmx:
        return redirect("rendering:pdf", render_id=render_row.id)

    response = render(
        request,
        "rendering/_status.html",
        {"render": render_row, "preview": preview},
    )
    # Cache miss -> 202 Accepted + polling fragment; HTMX cache hit -> 200.
    response.status_code = 200 if cache_hit else 202
    return response


# ---------------------------------------------------------------------------
# GET -> polling fragment
# ---------------------------------------------------------------------------
@login_required
@require_GET
def render_status_view(request, render_id):
    render_row = _get_owned_render(request.user, render_id)
    return render(
        request,
        "rendering/_status.html",
        {"render": render_row, "preview": bool(request.GET.get("preview"))},
    )


# ---------------------------------------------------------------------------
# GET -> stream the PDF
# ---------------------------------------------------------------------------
# The editor previews the PDF in an <iframe>; the global X-Frame-Options:
# DENY would blank it, so allow same-origin framing for this view only.
@xframe_options_sameorigin
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


# ---------------------------------------------------------------------------
# History and share links
# ---------------------------------------------------------------------------
SHARE_DURATIONS = {"1d": 1, "7d": 7, "30d": 30}


@login_required
@require_GET
def history_view(request, cv_id):
    cv = get_object_or_404(CV, pk=cv_id, user=request.user)
    renders = cv.renders.prefetch_related("share_links")[:50]
    return render(request, "rendering/history.html", {"cv": cv, "renders": renders})


@login_required
@require_POST
def share_create_view(request, render_id):
    from datetime import timedelta

    from django.contrib import messages
    from django.utils import timezone

    from .models import ShareLink

    render_row = _get_owned_render(request.user, render_id)
    if render_row.status != RenderStatus.DONE or not render_row.pdf_file:
        raise Http404("PDF not ready")
    days = SHARE_DURATIONS.get(request.POST.get("duration", "7d"), 7)
    ShareLink.objects.create(render=render_row, expires_at=timezone.now() + timedelta(days=days))
    messages.success(request, f"Share link created; it expires in {days} day(s).")
    return redirect("rendering:history", cv_id=render_row.cv_id)


@login_required
@require_POST
def share_revoke_view(request, link_id):
    from django.contrib import messages

    from .models import ShareLink

    link = get_object_or_404(ShareLink, pk=link_id, render__cv__user=request.user)
    link.revoked = True
    link.save(update_fields=["revoked"])
    messages.success(request, "Share link revoked.")
    return redirect("rendering:history", cv_id=link.render.cv_id)


@require_GET
def shared_pdf_view(request, token):
    """Public: anyone holding a live token can read that one PDF."""
    from django.db.models import F

    from .models import ShareLink

    link = get_object_or_404(ShareLink.objects.select_related("render__cv"), token=token)
    if not link.is_active or not link.render.pdf_file:
        raise Http404("This link has expired or was revoked.")
    ShareLink.objects.filter(pk=link.pk).update(view_count=F("view_count") + 1)
    response = FileResponse(
        link.render.pdf_file.open("rb"),
        content_type="application/pdf",
        filename=f"{link.render.cv.alias or 'cv'}.pdf",
    )
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Cache-Control"] = "private, no-store"
    return response
