"""Mounted at /api/v1/ under the ``api`` namespace."""

from __future__ import annotations

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.routers import DefaultRouter

from .views import CVViewSet, EntryViewSet, RenderViewSet, SectionViewSet

app_name = "api"

router = DefaultRouter()
router.register("cvs", CVViewSet, basename="cv")
router.register("sections", SectionViewSet, basename="section")
router.register("entries", EntryViewSet, basename="entry")
router.register("renders", RenderViewSet, basename="render")

urlpatterns = [
    path("", include(router.urls)),
    # The schema describes shapes, not data, so it's public; the interactive
    # docs are staff-only (roadmap Phase 5).
    path("schema/", SpectacularAPIView.as_view(permission_classes=[AllowAny]), name="schema"),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="api:schema", permission_classes=[IsAdminUser]),
        name="docs",
    ),
]
