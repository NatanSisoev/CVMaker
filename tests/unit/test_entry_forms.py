"""Entry forms: the shared original-language (``canonical_language``) field."""

from __future__ import annotations

import pytest

from entries.forms import BulletEntryForm, PublicationEntryForm
from tests.factories import BulletEntryFactory, PublicationEntryFactory

pytestmark = pytest.mark.django_db


def test_every_entry_form_exposes_original_language():
    from entries.views import ENTRY_FORMS

    for form_class in ENTRY_FORMS.values():
        assert "canonical_language" in form_class().fields, form_class.__name__


def test_code_is_normalised_and_saved(user):
    entry = BulletEntryFactory(user=user)
    form = BulletEntryForm(
        {"alias": entry.alias, "bullet": "hola", "canonical_language": " ES "}, instance=entry
    )
    assert form.is_valid(), form.errors
    assert form.save().canonical_language == "es"


def test_blank_keeps_current_language(user):
    entry = BulletEntryFactory(user=user, canonical_language="fr")
    form = BulletEntryForm({"alias": entry.alias, "bullet": "x"}, instance=entry)
    assert form.is_valid(), form.errors
    assert form.save().canonical_language == "fr"


def test_new_entry_defaults_to_en(user):
    form = BulletEntryForm({"alias": "fresh", "bullet": "x"})
    assert form.is_valid(), form.errors
    entry = form.save(commit=False)
    entry.user = user
    entry.save()
    assert entry.canonical_language == "en"


@pytest.mark.parametrize("code", ["e", "eng", "1a", "e-"])
def test_malformed_code_rejected(user, code):
    entry = BulletEntryFactory(user=user)
    form = BulletEntryForm(
        {"alias": entry.alias, "bullet": "x", "canonical_language": code}, instance=entry
    )
    assert not form.is_valid()
    assert "canonical_language" in form.errors


def test_switching_onto_an_existing_translation_is_refused(user):
    entry = PublicationEntryFactory(user=user, translations={"es": {"title": "T"}})
    form = PublicationEntryForm(
        {"alias": entry.alias, "title": "x", "authors": "a", "canonical_language": "es"},
        instance=entry,
    )
    assert not form.is_valid()
    assert "ES translation" in form.errors["canonical_language"][0]
