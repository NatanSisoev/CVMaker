"""/api/v1 views (Phase 5): read access to your CVs, sections and entries,
plus render-and-download. Auth: personal token (``Authorization: Token <key>``)
or the browser session. Everything is scoped to ``request.user``; other users'
ids are indistinguishable from missing ones (404).
"""

from __future__ import annotations

from django.http import FileResponse, Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from cv.models import CV
from entries.models import BaseEntry
from rendering.models import Render, RenderStatus
from rendering.services import enqueue_render
from sections.models import Section

from .serializers import (
    CVSerializer,
    EntrySerializer,
    RenderRequestSerializer,
    RenderSerializer,
    SectionSerializer,
)


class CVViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CV.objects.none()  # schema introspection only; see get_queryset
    serializer_class = CVSerializer
    throttle_scope: str | None = None  # set per-action (render); DRF needs the attribute

    def get_queryset(self):
        return (
            CV.objects.filter(user=self.request.user)
            .select_related("design", "locale")
            .order_by("-modified_date")
        )

    @extend_schema(
        request=RenderRequestSerializer,
        responses={
            200: OpenApiResponse(RenderSerializer, description="Cache hit: already rendered."),
            202: OpenApiResponse(RenderSerializer, description="Queued; poll the render."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        throttle_classes=[ScopedRateThrottle],
        throttle_scope="render",
    )
    def render(self, request, pk=None):
        """Render the CV (optionally in another language/style). Identical
        inputs are served from cache."""
        cv = self.get_object()
        params = RenderRequestSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        render = enqueue_render(
            cv,
            language=params.validated_data["language"],
            style=params.validated_data["style"],
            requested_by=request.user,
        )
        cached = render.status == RenderStatus.DONE and bool(render.pdf_file)
        return Response(
            RenderSerializer(render, context={"request": request}).data,
            status=status.HTTP_200_OK if cached else status.HTTP_202_ACCEPTED,
        )


class SectionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Section.objects.none()  # schema introspection only; see get_queryset
    serializer_class = SectionSerializer

    def get_queryset(self):
        return (
            Section.objects.filter(user=self.request.user)
            .prefetch_related("section_entries")
            .order_by("title")
        )


class EntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BaseEntry.objects.none()  # schema introspection only; see get_queryset
    serializer_class = EntrySerializer

    def get_queryset(self):
        return (
            BaseEntry.objects.filter(user=self.request.user).select_subclasses().order_by("alias")
        )


class RenderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Render.objects.none()  # schema introspection only; see get_queryset
    serializer_class = RenderSerializer

    def get_queryset(self):
        return Render.objects.filter(cv__user=self.request.user).order_by("-requested_at")

    @extend_schema(
        responses={
            (200, "application/pdf"): OpenApiResponse(description="The rendered PDF."),
            404: OpenApiResponse(description="Not found, or not done yet."),
        }
    )
    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        render = self.get_object()
        if render.status != RenderStatus.DONE or not render.pdf_file:
            raise Http404("PDF not ready")
        return FileResponse(
            render.pdf_file.open("rb"),
            content_type="application/pdf",
            filename=f"{render.cv.alias or 'cv'}.pdf",
        )
