"""Unit tests for the entry models and their serialize() contracts.

These exist to pin the rendercv-payload shape. A contract change should
break these tests loudly so we catch it before it reaches the renderer.
"""

from __future__ import annotations

import datetime as dt

import pytest

from entries.models import get_entry_model
from tests.factories import (
    BulletEntryFactory,
    EducationEntryFactory,
    ExperienceEntryFactory,
    PublicationEntryFactory,
    TextEntryFactory,
)

pytestmark = pytest.mark.django_db


def test_get_entry_model_resolves_known():
    from entries.models import EducationEntry

    assert get_entry_model("EducationEntry") is EducationEntry


def test_get_entry_model_raises_on_unknown():
    with pytest.raises(ValueError, match="Unable to determine entry model"):
        get_entry_model("NotARealEntry")


def test_education_serialize_drops_blanks():
    entry = EducationEntryFactory(summary="", highlights="")
    payload = entry.serialize()
    assert "summary" not in payload
    assert "highlights" not in payload
    assert payload["institution"]
    assert payload["area"]


def test_education_serialize_preserves_dates():
    entry = EducationEntryFactory(
        start_date=dt.date(2020, 1, 1),
        end_date=dt.date(2024, 1, 1),
    )
    payload = entry.serialize()
    assert payload["start_date"] == "2020-01-01"
    assert payload["end_date"] == "2024-01-01"


def test_experience_serialize_custom_date_overrides_range():
    entry = ExperienceEntryFactory(
        start_date=dt.date(2020, 1, 1),
        end_date=dt.date(2024, 1, 1),
        date=dt.date(2025, 6, 1),
    )
    payload = entry.serialize()
    assert payload["date"] == "2025-06-01"
    assert "start_date" not in payload
    assert "end_date" not in payload


def test_bullet_serialize_shape():
    entry = BulletEntryFactory(bullet="Led the rebrand.")
    assert entry.serialize() == {"bullet": "Led the rebrand."}


def test_text_serialize_shape():
    entry = TextEntryFactory(text="Long-form narrative.")
    assert entry.serialize() == {"text": "Long-form narrative."}


def test_publication_serialize_drops_blanks():
    entry = PublicationEntryFactory(doi="", url="", journal="")
    payload = entry.serialize()
    assert "doi" not in payload
    assert "url" not in payload
    assert "journal" not in payload
    assert payload["title"]
    assert payload["authors"]


def test_highlights_parsed_by_semicolon():
    entry = EducationEntryFactory(
        highlights="led thing one; led thing two; ; led thing three"
    )
    payload = entry.serialize()
    assert payload["highlights"] == ["led thing one", "led thing two", "led thing three"]
