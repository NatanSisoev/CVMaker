"""Unit tests for per-entry translations (Phase 2.2 / ADR-0006).

Pin the contract for ``BaseEntry.get_field``, ``BaseEntry.clean``, and
each subclass's ``serialize(language=…)`` payload. A regression here
silently shadows render output, so the tests must be loud.
"""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from entries.models import EducationEntry
from tests.factories import (
    BulletEntryFactory,
    EducationEntryFactory,
    ExperienceEntryFactory,
    PublicationEntryFactory,
    TextEntryFactory,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# get_field — the workhorse
# ---------------------------------------------------------------------------
class TestGetField:
    def test_canonical_language_returns_column_value(self):
        entry = EducationEntryFactory(
            summary="Master's thesis on graph algorithms.",
            canonical_language="en",
        )
        assert entry.get_field("summary", language="en") == "Master's thesis on graph algorithms."

    def test_none_language_returns_column_value(self):
        entry = EducationEntryFactory(summary="canonical text")
        assert entry.get_field("summary", language=None) == "canonical text"

    def test_translation_overrides_canonical(self):
        entry = EducationEntryFactory(
            summary="canonical",
            canonical_language="en",
            translations={"es": {"summary": "tesis"}},
        )
        assert entry.get_field("summary", language="es") == "tesis"
        # canonical untouched
        assert entry.get_field("summary", language="en") == "canonical"

    def test_missing_language_falls_back_to_canonical(self):
        entry = EducationEntryFactory(
            summary="canonical",
            canonical_language="en",
            translations={"es": {"summary": "tesis"}},
        )
        # No French translation -> fall back to English canonical.
        assert entry.get_field("summary", language="fr") == "canonical"

    def test_missing_field_in_present_language_falls_back(self):
        entry = EducationEntryFactory(
            summary="canonical summary",
            highlights="canonical highlights",
            canonical_language="en",
            # `es` covers `summary` but not `highlights`.
            translations={"es": {"summary": "resumen"}},
        )
        assert entry.get_field("summary", language="es") == "resumen"
        assert entry.get_field("highlights", language="es") == "canonical highlights"

    def test_explicit_empty_translation_returned_as_empty(self):
        """Per ADR-0006: an explicit empty string is a user signal, not a
        bug to fall back through."""
        entry = EducationEntryFactory(
            summary="canonical",
            canonical_language="en",
            translations={"es": {"summary": ""}},
        )
        assert entry.get_field("summary", language="es") == ""


# ---------------------------------------------------------------------------
# serialize() with a language
# ---------------------------------------------------------------------------
class TestSerializeWithLanguage:
    def test_education_serialize_picks_translation(self):
        entry = EducationEntryFactory(
            institution="MIT",
            area="Computer Science",
            summary="Worked on graph algorithms.",
            canonical_language="en",
            translations={
                "es": {
                    "area": "Ciencias de la Computación",
                    "summary": "Trabajé en algoritmos de grafos.",
                }
            },
        )
        es = entry.serialize(language="es")
        assert es["area"] == "Ciencias de la Computación"
        assert es["summary"] == "Trabajé en algoritmos de grafos."
        # Untranslatable / proper-noun field stays canonical.
        assert es["institution"] == "MIT"

    def test_education_serialize_no_language_returns_canonical(self):
        entry = EducationEntryFactory(
            area="Computer Science",
            translations={"es": {"area": "Ciencias de la Computación"}},
        )
        payload = entry.serialize()
        assert payload["area"] == "Computer Science"

    def test_bullet_serialize_translates(self):
        entry = BulletEntryFactory(
            bullet="Led the rebrand.",
            canonical_language="en",
            translations={"fr": {"bullet": "A mené la refonte."}},
        )
        assert entry.serialize(language="fr") == {"bullet": "A mené la refonte."}

    def test_text_serialize_translates(self):
        entry = TextEntryFactory(
            text="Narrative summary.",
            canonical_language="en",
            translations={"fr": {"text": "Résumé narratif."}},
        )
        assert entry.serialize(language="fr") == {"text": "Résumé narratif."}

    def test_experience_translates_position_and_summary(self):
        entry = ExperienceEntryFactory(
            company="Anthropic",
            position="Software Engineer",
            summary="Wrote code.",
            canonical_language="en",
            translations={
                "es": {"position": "Ingeniero de Software", "summary": "Escribí código."}
            },
        )
        es = entry.serialize(language="es")
        assert es["company"] == "Anthropic"  # company isn't translatable
        assert es["position"] == "Ingeniero de Software"
        assert es["summary"] == "Escribí código."

    def test_publication_title_translation_applies(self):
        entry = PublicationEntryFactory(
            title="A Paper About Things",
            authors="Alice Author, Bob Builder",
            canonical_language="en",
            translations={"es": {"title": "Un Artículo Sobre Cosas"}},
        )
        es = entry.serialize(language="es")
        assert es["title"] == "Un Artículo Sobre Cosas"
        # Authors stay canonical (not in TRANSLATABLE_FIELDS).
        assert es["authors"] == "Alice Author, Bob Builder"

    def test_highlights_parse_runs_after_translation(self):
        entry = EducationEntryFactory(
            highlights="first; second",
            canonical_language="en",
            translations={"es": {"highlights": "primero; segundo; tercero"}},
        )
        en = entry.serialize(language="en")
        es = entry.serialize(language="es")
        assert en["highlights"] == ["first", "second"]
        assert es["highlights"] == ["primero", "segundo", "tercero"]


# ---------------------------------------------------------------------------
# clean() validation — caught at form-submit time, not at render time
# ---------------------------------------------------------------------------
class TestClean:
    def test_clean_accepts_valid_translations(self):
        entry = EducationEntryFactory(
            translations={
                "es": {"summary": "resumen"},
                "fr": {"summary": "résumé", "highlights": "premier; deuxième"},
            },
        )
        # Should not raise.
        entry.clean()

    def test_clean_rejects_non_dict_translations(self):
        entry = EducationEntryFactory()
        entry.translations = ["not", "a", "dict"]
        with pytest.raises(ValidationError, match="must be a dict"):
            entry.clean()

    def test_clean_rejects_non_iso_language_key(self):
        entry = EducationEntryFactory()
        entry.translations = {"english": {"summary": "x"}}
        with pytest.raises(ValidationError, match="ISO 639-1"):
            entry.clean()

    def test_clean_rejects_unknown_field(self):
        entry = EducationEntryFactory()
        # institution is *not* in EducationEntry.TRANSLATABLE_FIELDS.
        entry.translations = {"es": {"institution": "MIT"}}
        with pytest.raises(ValidationError, match="unknown translatable fields"):
            entry.clean()

    def test_clean_rejects_typo(self):
        entry = EducationEntryFactory()
        entry.translations = {"es": {"summarry": "tipo"}}  # one r too many
        with pytest.raises(ValidationError, match="summarry"):
            entry.clean()

    def test_clean_rejects_non_dict_inner_bag(self):
        entry = EducationEntryFactory()
        entry.translations = {"es": "just a string"}
        with pytest.raises(ValidationError, match="must be a dict of field"):
            entry.clean()


# ---------------------------------------------------------------------------
# TRANSLATABLE_FIELDS declarations -- regression guard
# ---------------------------------------------------------------------------
def test_education_translatable_fields_declared():
    assert "summary" in EducationEntry.TRANSLATABLE_FIELDS
    assert "highlights" in EducationEntry.TRANSLATABLE_FIELDS
    assert "area" in EducationEntry.TRANSLATABLE_FIELDS
    # Non-translatable structural fields stay out.
    assert "institution" not in EducationEntry.TRANSLATABLE_FIELDS
    assert "start_date" not in EducationEntry.TRANSLATABLE_FIELDS
