"""Read serializers for /api/v1. Every queryset feeding them is user-scoped."""

from __future__ import annotations

from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from cv.models import CV, CVDesign
from cv.services import language_status
from entries.models import BaseEntry
from rendering.models import Render, RenderStatus
from sections.models import Section


class EntrySerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()

    class Meta:
        model = BaseEntry
        fields = ("id", "alias", "type", "canonical_language", "translations", "content")

    def get_type(self, entry) -> str:
        return entry.type

    @extend_schema_field(OpenApiTypes.ANY)
    def get_content(self, entry):
        """The entry in rendercv's shape, in its canonical language."""
        return entry.serialize()


class SectionSerializer(serializers.ModelSerializer):
    entries = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = ("id", "title", "alias", "entries")

    @extend_schema_field(serializers.ListField(child=serializers.UUIDField()))
    def get_entries(self, section):
        """Entry ids in display order."""
        return [se.entry_id for se in section.section_entries.all()]


class LanguageStatusSerializer(serializers.Serializer):
    code = serializers.CharField()
    done = serializers.IntegerField()
    total = serializers.IntegerField()


class CVSerializer(serializers.ModelSerializer):
    sections = serializers.SerializerMethodField()
    languages = serializers.SerializerMethodField()
    theme = serializers.SerializerMethodField()

    class Meta:
        model = CV
        fields = ("id", "alias", "theme", "created_date", "modified_date", "sections", "languages")

    @extend_schema_field(serializers.ListField(child=serializers.UUIDField()))
    def get_sections(self, cv):
        """Section ids in render order."""
        return list(cv.sections.order_by("cvsection__order").values_list("id", flat=True))

    @extend_schema_field(LanguageStatusSerializer(many=True))
    def get_languages(self, cv):
        """Renderable languages with translation completeness (active locale first)."""
        return language_status(cv)

    def get_theme(self, cv) -> str | None:
        return cv.design.theme if cv.design_id else None


class RenderRequestSerializer(serializers.Serializer):
    language = serializers.RegexField(r"^([a-z]{2})?$", required=False, default="")
    style = serializers.ChoiceField(
        choices=[("", "CV default")] + [c for c in CVDesign.THEME_CHOICES if c[0] != "custom"],
        required=False,
        default="",
    )


class RenderSerializer(serializers.ModelSerializer):
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Render
        fields = (
            "id",
            "cv",
            "language",
            "style",
            "status",
            "error",
            "requested_at",
            "completed_at",
            "pdf_url",
        )

    def get_pdf_url(self, render) -> str | None:
        """Absolute URL of the PDF once the render is done, else null."""
        if render.status != RenderStatus.DONE or not render.pdf_file:
            return None
        path = reverse("api:render-pdf", kwargs={"pk": render.pk})
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path
