"""
Entry models.

Phase 2.2 (ADR-0006) adds per-entry translations:

  - ``canonical_language``: the source language of the row's column values.
  - ``translations``: a JSONField bag keyed by ISO 639-1 code, holding
    field-level overrides. Reads use ``get_field(name, language=…)`` which
    falls back to the canonical column value when no translation is
    present.

Each subclass declares ``TRANSLATABLE_FIELDS`` -- the tuple of column
names that participate in translation. ``serialize(language=…)`` walks
those columns through ``get_field`` and writes everything else straight
off the row.
"""

import uuid
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from model_utils.managers import InheritanceManager

# ---------------------------------------------------------------------------
# Registry: rendercv-style entry-type strings -> Django model class.
# Populated at the bottom of this module after each subclass is defined.
# ---------------------------------------------------------------------------
_ENTRY_MODELS_BY_NAME: dict[str, type["BaseEntry"]] = {}


def get_entry_model(entry_type: str) -> type["BaseEntry"]:
    """Resolve an entry class name to its model. Raises on unknown types."""
    try:
        return _ENTRY_MODELS_BY_NAME[entry_type]
    except KeyError as exc:
        raise ValueError(
            f"Unable to determine entry model from type: {entry_type!r}. "
            f"Known types: {sorted(_ENTRY_MODELS_BY_NAME)}"
        ) from exc


# ---------------------------------------------------------------------------
# BaseEntry -- concrete (not abstract) so SectionEntry can FK to it (ADR-0005).
# Also the home for the translations bag and the shared get_field helper.
# ---------------------------------------------------------------------------
class BaseEntry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        related_name="%(class)s",
    )
    alias = models.CharField(
        max_length=20, null=False, blank=False, help_text="Alias for the CV entry"
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)

    # ------------------------------------------------------------------
    # Translation storage (Phase 2.2 / ADR-0006)
    # ------------------------------------------------------------------
    canonical_language = models.CharField(
        max_length=2,
        default="en",
        help_text="ISO 639-1 code identifying the language the canonical columns are written in.",
    )
    translations: models.JSONField = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Per-language field overrides keyed by ISO 639-1 code, "
            'e.g. {"es": {"summary": "..."}, "fr": {"summary": "..."}}'
        ),
    )

    objects = InheritanceManager()

    type = "base"

    # Override per subclass. Empty here because BaseEntry has no
    # translatable columns of its own -- every translatable field lives on
    # a subclass.
    TRANSLATABLE_FIELDS: ClassVar[tuple[str, ...]] = ()

    # TYPE-HINTING FOR METHODS
    start_date: models.DateField
    end_date: models.DateField
    date: models.DateField
    summary: models.CharField
    highlights: models.CharField

    def __str__(self) -> str:
        return f"[{self.__class__.__name__}({self.alias})]"

    # ------------------------------------------------------------------
    # Translation helpers
    # ------------------------------------------------------------------
    def get_field(self, name: str, language: str | None = None) -> str:
        """Return the value of ``name``, translated to ``language`` if
        possible, else falling back to the canonical column value.

        Fallback rules (per ADR-0006):

          1. If ``language`` is ``None`` or matches ``canonical_language``,
             return the canonical column value as-is.
          2. If ``language`` is in ``translations`` AND that bag has
             ``name``, return it -- even if it's an empty string. Empty
             strings are an explicit user signal ("blank in this lang").
          3. Otherwise, fall back to the canonical column value.
        """
        canonical = getattr(self, name, "")

        if language is None or language == self.canonical_language:
            return canonical

        bag = self.translations.get(language) if isinstance(self.translations, dict) else None
        if isinstance(bag, dict) and name in bag:
            return bag[name]

        return canonical

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def clean(self) -> None:
        """Validate the shape of ``translations``.

        - Top-level keys must be 2-letter ISO 639-1 codes.
        - Each value must be a dict.
        - Inner keys must be in this subclass's ``TRANSLATABLE_FIELDS``.

        Catches typos at form-submit time instead of letting them sit in
        the database silently shadowing render output.
        """
        super().clean()

        if not isinstance(self.translations, dict):
            raise ValidationError(
                {"translations": "translations must be a dict keyed by language code"}
            )

        valid_fields = set(self.TRANSLATABLE_FIELDS)
        for lang, bag in self.translations.items():
            if not isinstance(lang, str) or len(lang) != 2 or not lang.isalpha():
                raise ValidationError(
                    {
                        "translations": (
                            f"language key must be a 2-letter ISO 639-1 code, got {lang!r}"
                        )
                    }
                )
            if not isinstance(bag, dict):
                raise ValidationError(
                    {
                        "translations": (
                            f"translations[{lang!r}] must be a dict of field -> value, "
                            f"got {type(bag).__name__}"
                        )
                    }
                )
            unknown = set(bag) - valid_fields
            if unknown:
                raise ValidationError(
                    {
                        "translations": (
                            f"unknown translatable fields for "
                            f"{self.__class__.__name__}: {sorted(unknown)}. "
                            f"Allowed: {sorted(valid_fields)}"
                        )
                    }
                )

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------
    def _format_dates(self) -> dict:
        # Some entry subclasses (e.g. PublicationEntry) only carry ``date``
        # and don't define ``start_date`` / ``end_date`` columns. Use getattr
        # so this method works uniformly across the polymorphic hierarchy.
        if getattr(self, "date", None):
            return {"date": self.date.isoformat()}

        dates = {}
        start = getattr(self, "start_date", None)
        end = getattr(self, "end_date", None)
        if start:
            dates["start_date"] = start.isoformat()
        if end:
            dates["end_date"] = end.isoformat()

        return dates

    def _parse_highlights(self, language: str | None = None) -> list | None:
        raw = (
            self.get_field("highlights", language=language)
            if "highlights" in self.TRANSLATABLE_FIELDS
            else getattr(self, "highlights", "")
        )
        if not raw:
            return None
        return [highlight.strip() for highlight in raw.split(";") if highlight.strip()]


# ---------------------------------------------------------------------------
# EducationEntry
# ---------------------------------------------------------------------------
class EducationEntry(BaseEntry):
    institution = models.CharField(
        max_length=100, null=False, blank=False, help_text="The name of the institution"
    )
    area = models.CharField(max_length=100, null=False, blank=False, help_text="The area of study")

    degree = models.CharField(
        max_length=100, blank=True, help_text="The type of degree (e.g., BS, MS, PhD)"
    )
    location = models.CharField(max_length=100, blank=True, help_text="The location")
    start_date = models.DateField(null=True, blank=True, help_text="The start date")
    end_date = models.DateField(null=True, blank=True, help_text="The end date")
    date = models.DateField(
        null=True, blank=True, help_text="Custom date (overrides start_date and end_date)"
    )
    summary = models.CharField(max_length=500, blank=True, help_text="Summary of the entry")
    highlights = models.CharField(
        max_length=500, blank=True, help_text="List of highlights separated by ;"
    )

    type = "education"

    # Translatable: anything a user might phrase differently in another
    # language. ``institution`` is left out -- proper noun by default; users
    # can override per-instance via translations[lang]["institution"]
    # if their school's name does in fact differ across languages, though
    # that requires extending TRANSLATABLE_FIELDS at the model level.
    TRANSLATABLE_FIELDS: ClassVar[tuple[str, ...]] = (
        "area",
        "degree",
        "location",
        "summary",
        "highlights",
    )

    def __str__(self) -> str:
        return f"[{self.institution}({self.area})]"

    def serialize(self, language: str | None = None) -> dict:
        info = {
            "institution": self.institution,
            "area": self.get_field("area", language=language),
            "degree": self.get_field("degree", language=language) or None,
            "location": self.get_field("location", language=language) or None,
            **self._format_dates(),
            "summary": self.get_field("summary", language=language) or None,
            "highlights": self._parse_highlights(language=language),
        }
        return {k: v for k, v in info.items() if v is not None}


# ---------------------------------------------------------------------------
# ExperienceEntry
# ---------------------------------------------------------------------------
class ExperienceEntry(BaseEntry):
    company = models.CharField(
        max_length=100, null=False, blank=False, help_text="The name of the company"
    )
    position = models.CharField(max_length=100, null=False, blank=False, help_text="The position")

    location = models.CharField(max_length=100, blank=True, help_text="The location")
    start_date = models.DateField(null=True, blank=True, help_text="The start date")
    end_date = models.DateField(null=True, blank=True, help_text="The end date")
    date = models.DateField(
        null=True, blank=True, help_text="Custom date (overrides start_date and end_date)"
    )
    summary = models.CharField(max_length=500, blank=True, help_text="Summary of the entry")
    highlights = models.CharField(
        max_length=500, blank=True, help_text="List of highlights separated by ;"
    )

    type = "experience"

    TRANSLATABLE_FIELDS: ClassVar[tuple[str, ...]] = (
        "position",
        "location",
        "summary",
        "highlights",
    )

    def __str__(self) -> str:
        return f"[{self.company}({self.position})]"

    def serialize(self, language: str | None = None) -> dict:
        info = {
            "company": self.company,
            "position": self.get_field("position", language=language),
            "location": self.get_field("location", language=language) or None,
            **self._format_dates(),
            "summary": self.get_field("summary", language=language) or None,
            "highlights": self._parse_highlights(language=language),
        }
        return {k: v for k, v in info.items() if v is not None}


# ---------------------------------------------------------------------------
# NormalEntry
# ---------------------------------------------------------------------------
class NormalEntry(BaseEntry):
    name = models.CharField(
        max_length=100, null=False, blank=False, help_text="The name of the entry"
    )

    location = models.CharField(max_length=100, blank=True, help_text="The location")
    start_date = models.DateField(null=True, blank=True, help_text="The start date")
    end_date = models.DateField(null=True, blank=True, help_text="The end date")
    date = models.DateField(
        null=True, blank=True, help_text="Custom date (overrides start_date and end_date)"
    )
    summary = models.CharField(max_length=500, blank=True, help_text="Summary of the entry")
    highlights = models.CharField(
        max_length=500, blank=True, help_text="List of highlights separated by ;"
    )

    type = "normal"

    TRANSLATABLE_FIELDS: ClassVar[tuple[str, ...]] = (
        "name",
        "location",
        "summary",
        "highlights",
    )

    def __str__(self) -> str:
        return f"[{self.name}]"

    def serialize(self, language: str | None = None) -> dict:
        info = {
            "name": self.get_field("name", language=language),
            "location": self.get_field("location", language=language) or None,
            **self._format_dates(),
            "summary": self.get_field("summary", language=language) or None,
            "highlights": self._parse_highlights(language=language),
        }
        return {k: v for k, v in info.items() if v is not None}


# ---------------------------------------------------------------------------
# PublicationEntry
# ---------------------------------------------------------------------------
class PublicationEntry(BaseEntry):
    title = models.CharField(
        max_length=200, null=False, blank=False, help_text="The title of the publication"
    )
    authors = models.CharField(
        max_length=300, null=False, blank=False, help_text="The authors (separated by commas)"
    )

    type = "publication"

    doi = models.CharField(max_length=100, blank=True, help_text="The DOI of the publication")
    url = models.URLField(blank=True, help_text="The URL of the publication")
    journal = models.CharField(
        max_length=200, blank=True, help_text="The journal of the publication"
    )
    date = models.DateField(
        null=True, blank=True, help_text="Custom date (overrides start_date and end_date)"
    )

    # Title translations are uncommon in academia -- citations should match
    # how the work is published -- but legitimate for non-English-published
    # work being shown to English readers. Authors stay canonical.
    TRANSLATABLE_FIELDS: ClassVar[tuple[str, ...]] = ("title", "journal")

    def __str__(self) -> str:
        return f"[{self.title}]"

    def serialize(self, language: str | None = None) -> dict:
        info = {
            "title": self.get_field("title", language=language),
            "authors": self.authors,
            "doi": self.doi if self.doi else None,
            "url": self.url if self.url else None,
            "journal": self.get_field("journal", language=language) or None,
            **self._format_dates(),
        }
        return {k: v for k, v in info.items() if v is not None}


# ---------------------------------------------------------------------------
# OneLineEntry / BulletEntry / NumberedEntry / ReversedNumberedEntry / TextEntry
# ---------------------------------------------------------------------------
class OneLineEntry(BaseEntry):
    label = models.CharField(
        max_length=100, null=False, blank=False, help_text="The label of the entry"
    )
    details = models.CharField(
        max_length=300, null=False, blank=False, help_text="The details of the entry"
    )

    type = "one-line"

    TRANSLATABLE_FIELDS: ClassVar[tuple[str, ...]] = ("label", "details")

    def __str__(self) -> str:
        return f"[{self.label}({self.details})]"

    def serialize(self, language: str | None = None) -> dict:
        return {
            "label": self.get_field("label", language=language),
            "details": self.get_field("details", language=language),
        }


class BulletEntry(BaseEntry):
    bullet = models.CharField(max_length=300, null=False, blank=False, help_text="The bullet point")

    type = "bullet"

    TRANSLATABLE_FIELDS: ClassVar[tuple[str, ...]] = ("bullet",)

    def __str__(self) -> str:
        return f"[Bulleted({self.bullet})]"

    def serialize(self, language: str | None = None) -> dict:
        return {"bullet": self.get_field("bullet", language=language)}


class NumberedEntry(BaseEntry):
    number = models.CharField(
        max_length=300, null=False, blank=False, help_text="The numbered entry content"
    )

    type = "numbered"

    TRANSLATABLE_FIELDS: ClassVar[tuple[str, ...]] = ("number",)

    def __str__(self) -> str:
        return f"[Numbered({self.number})]"

    def serialize(self, language: str | None = None) -> dict:
        return {"number": self.get_field("number", language=language)}


class ReversedNumberedEntry(BaseEntry):
    reversed_number = models.CharField(
        max_length=300, null=False, blank=False, help_text="The reversed numbered entry content"
    )

    type = "reversed-numbered"

    TRANSLATABLE_FIELDS: ClassVar[tuple[str, ...]] = ("reversed_number",)

    def __str__(self) -> str:
        return f"[ReversedNumbered({self.reversed_number})]"

    def serialize(self, language: str | None = None) -> dict:
        return {"reversed_number": self.get_field("reversed_number", language=language)}


class TextEntry(BaseEntry):
    text = models.TextField(null=False, blank=False, help_text="The text content for the entry")

    type = "text"

    TRANSLATABLE_FIELDS: ClassVar[tuple[str, ...]] = ("text",)

    def __str__(self) -> str:
        return f"[Text({self.text})]"

    def serialize(self, language: str | None = None) -> dict:
        return {"text": self.get_field("text", language=language)}


# ---------------------------------------------------------------------------
# Registry — populated after the classes above are defined. Used by
# get_entry_model() to resolve rendercv-style type names to Django models.
# ---------------------------------------------------------------------------
_ENTRY_MODELS_BY_NAME.update(
    {
        "EducationEntry": EducationEntry,
        "ExperienceEntry": ExperienceEntry,
        "PublicationEntry": PublicationEntry,
        "NormalEntry": NormalEntry,
        "OneLineEntry": OneLineEntry,
        "BulletEntry": BulletEntry,
        "NumberedEntry": NumberedEntry,
        "ReversedNumberedEntry": ReversedNumberedEntry,
        "TextEntry": TextEntry,
    }
)
