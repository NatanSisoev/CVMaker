"""cv.services.language_status -- the data behind the Editor's LanguageChips."""

from __future__ import annotations

import pytest

from cv.models import CVLocale
from cv.services import available_languages, language_status
from sections.models import CVSection, SectionEntry
from tests.factories import CVFactory, ExperienceEntryFactory, SectionFactory

pytestmark = pytest.mark.django_db


def _attach(cv, *entries):
    section = SectionFactory(user=cv.user)
    for order, entry in enumerate(entries):
        SectionEntry.objects.create(section=section, entry=entry, order=order)
    CVSection.objects.create(cv=cv, section=section, order=0)


def _by_code(cv):
    return {s["code"]: (s["done"], s["total"]) for s in language_status(cv)}


def test_empty_cv_has_no_languages():
    assert language_status(CVFactory()) == []


def test_complete_partial_and_missing():
    cv = CVFactory()
    full = ExperienceEntryFactory(
        user=cv.user,
        summary="",
        highlights="",
        translations={"es": {"position": "P", "location": "L"}},
    )
    partial = ExperienceEntryFactory(
        user=cv.user, summary="", highlights="", translations={"es": {"position": "P"}}
    )
    _attach(cv, full, partial)

    status = _by_code(cv)
    assert status["en"] == (2, 2)  # canonical counts as done
    assert status["es"] == (1, 2)  # `partial` lacks location


def test_explicit_empty_translation_counts_as_done():
    cv = CVFactory()
    entry = ExperienceEntryFactory(
        user=cv.user,
        summary="",
        highlights="",
        translations={"fr": {"position": "", "location": ""}},
    )
    _attach(cv, entry)
    assert _by_code(cv)["fr"] == (1, 1)


def test_active_locale_first_even_without_translations():
    cv = CVFactory()
    cv.locale = CVLocale.objects.create(user=cv.user, language="de")
    cv.save()
    _attach(cv, ExperienceEntryFactory(user=cv.user))

    status = language_status(cv)
    assert status[0] == {"code": "de", "done": 0, "total": 1}
    assert available_languages(cv) == ["de", "en"]


def test_only_entries_in_this_cv_count():
    cv = CVFactory()
    _attach(cv, ExperienceEntryFactory(user=cv.user))
    ExperienceEntryFactory(user=cv.user, translations={"it": {}})  # not in the CV
    assert "it" not in _by_code(cv)
