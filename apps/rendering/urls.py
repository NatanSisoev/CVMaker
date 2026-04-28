"""URL patterns for the rendering app.

Phase 3.1 ships the URL skeleton; Phase 3.4 wires the actual views.
The pattern names are pinned now so other apps can ``reverse()`` them
once the views land.
"""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "rendering"

urlpatterns = [
    # POST -> enqueue a render for the CV; returns 202 with the polling URL.
    path("cv/<uuid:cv_id>/render/", views.enqueue_render_view, name="enqueue"),
    # GET -> return the Render's status fragment (HTMX polls this).
    path("render/<uuid:render_id>/", views.render_status_view, name="status"),
    # GET -> stream the finished PDF.
    path("render/<uuid:render_id>/pdf/", views.render_pdf_view, name="pdf"),
]
