"""Every entry kind, fully populated, through the real rendercv + Typst pipeline.

Serializer shapes drift from rendercv's schema silently (publications sent
``authors`` as a string and text entries as a mapping until 2026-10-08), and
only an actual render notices. One section per kind, so a failure names it.
"""

from __future__ import annotations

import datetime

import pytest

from cv.models import CVInfo
from cv.services import build_render_payload
from rendering import tasks
from sections.models import CVSection, SectionEntry
from tests import factories as f

pytestmark = pytest.mark.django_db

D = datetime.date

KINDS = {
    "Education": lambda u: f.EducationEntryFactory(
        user=u,
        institution="University of London",
        area="Mathematics",
        degree="BS",
        location="London",
        start_date=D(1830, 9, 1),
        end_date=D(1834, 6, 1),
        summary="Studied analysis.",
        highlights="First class; Thesis on series",
    ),
    "Experience": lambda u: f.ExperienceEntryFactory(
        user=u,
        company="Analytical Engines",
        position="Programmer",
        location="London",
        start_date=D(1842, 1, 1),
        summary="Wrote programs.",
        highlights="Bernoulli numbers; Loops",
    ),
    "Normal": lambda u: f.NormalEntryFactory(
        user=u,
        name="Difference Engine talk",
        location="Turin",
        date=D(1840, 5, 1),
        summary="Invited lecture.",
        highlights="Well received",
    ),
    "Publication": lambda u: f.PublicationEntryFactory(
        user=u,
        title="Notes on the Analytical Engine",
        authors="Ada Lovelace, Charles Babbage",
        doi="10.1000/xyz123",
        url="https://example.com/notes",
        journal="Scientific Memoirs",
        date=D(1843, 10, 1),
    ),
    "OneLine": lambda u: f.OneLineEntryFactory(
        user=u, label="Languages", details="English, French"
    ),
    "Bullet": lambda u: f.BulletEntryFactory(user=u, bullet="Corresponded with Faraday"),
    "Numbered": lambda u: f.NumberedEntryFactory(user=u, number="First item"),
    "ReversedNumbered": lambda u: f.ReversedNumberedEntryFactory(
        user=u, reversed_number="Last item"
    ),
    "Text": lambda u: f.TextEntryFactory(user=u, text="A paragraph of free text."),
}


def _cv_with(user, kinds, translations=None):
    info = CVInfo.objects.create(
        user=user, alias="me", name="Ada Lovelace", email="ada@example.com"
    )
    cv = f.CVFactory(user=user, info=info)
    for order, kind in enumerate(kinds):
        entry = KINDS[kind](user)
        if translations:
            entry.translations = translations(entry)
            entry.save()
        section = f.SectionFactory(user=user, title=f"{kind} section")
        SectionEntry.objects.create(section=section, entry=entry, order=0)
        CVSection.objects.create(cv=cv, section=section, order=order)
    return cv


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_each_kind_renders(user, kind):
    cv = _cv_with(user, [kind])
    pdf = tasks._render_payload_to_pdf(build_render_payload(cv))
    assert pdf.startswith(b"%PDF")


def test_all_kinds_together_render_in_spanish(user):
    def spanish(entry):
        return {
            "es": {
                field: f"ES {getattr(entry, field)}"
                for field in entry.TRANSLATABLE_FIELDS
                if getattr(entry, field, "")
            }
        }

    cv = _cv_with(user, sorted(KINDS), translations=spanish)
    payload = build_render_payload(cv, language="es")
    sections = payload["cv"]["sections"]
    assert sections["Text section"] == ["ES A paragraph of free text."]
    pdf = tasks._render_payload_to_pdf(payload)
    assert pdf.startswith(b"%PDF")


def test_language_override_works_without_a_cvlocale(user):
    cv = _cv_with(user, ["Bullet"], translations=lambda e: {"fr": {"bullet": "Bonjour"}})
    assert cv.locale is None
    payload = build_render_payload(cv, language="fr")
    assert payload["cv"]["sections"]["Bullet section"] == [{"bullet": "Bonjour"}]
    assert build_render_payload(cv)["cv"]["sections"]["Bullet section"] == [
        {"bullet": "Corresponded with Faraday"}
    ]


def test_sections_render_in_cvsection_order(user):
    cv = _cv_with(user, ["Bullet", "Text", "OneLine"])
    # Reverse the order the way the editor's drag-reorder does.
    from sections.services import reorder_sections

    ids = list(cv.sections.order_by("cvsection__order").values_list("id", flat=True))
    reorder_sections(cv, list(reversed(ids)))

    titles = list(build_render_payload(cv)["cv"]["sections"])
    assert titles == ["OneLine section", "Text section", "Bullet section"]
