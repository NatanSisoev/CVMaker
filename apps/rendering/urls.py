"""URL patterns for the rendering app.

All routes live under ``/renders/`` to avoid colliding with ``cv.urls``
(which already owns ``/cv/``). Mounted in the root urlconf as
``path("", include("rendering.urls", namespace="rendering"))``.
"""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "rendering"

urlpatterns = [
    # POST -> enqueue a render for the CV; returns 202 + polling fragment
    # on cache miss, or 302 -> PDF on cache hit.
    path("renders/cv/<uuid:cv_id>/", views.enqueue_render_view, name="enqueue"),
    # GET -> the polling fragment.
    path("renders/<uuid:render_id>/", views.render_status_view, name="status"),
    # GET -> stream the finished PDF.
    path("renders/<uuid:render_id>/pdf/", views.render_pdf_view, name="pdf"),
]
