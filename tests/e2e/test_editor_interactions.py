"""Editor interactions in a real browser: drag-reorder, translations, palette.

These cover the client-side code paths (Sortable, HTMX fragments, Alpine
state) that the HTML-level integration tests can only assert markup for.
"""

from __future__ import annotations

import re

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


@pytest.fixture
def cv(logged_in):
    """A CV with two sections; the first holds three bullet entries."""
    from cv.models import CVInfo
    from sections.models import CVSection, SectionEntry
    from tests.factories import BulletEntryFactory, CVFactory, SectionFactory

    info = CVInfo.objects.create(user=logged_in, alias="me", name="Grace Hopper")
    cv = CVFactory(user=logged_in, alias="navy-cv", info=info)
    first = SectionFactory(user=logged_in, title="Achievements")
    second = SectionFactory(user=logged_in, title="Talks")
    for order, alias in enumerate(("alpha", "bravo", "charlie")):
        entry = BulletEntryFactory(user=logged_in, alias=alias, bullet=f"{alias} text")
        SectionEntry.objects.create(section=first, entry=entry, order=order)
    SectionEntry.objects.create(
        section=second, entry=BulletEntryFactory(user=logged_in, alias="delta"), order=0
    )
    CVSection.objects.create(cv=cv, section=first, order=0)
    CVSection.objects.create(cv=cv, section=second, order=1)
    return cv


def _entry_order(section_title):
    from sections.models import SectionEntry

    return list(
        SectionEntry.objects.filter(section__title=section_title)
        .order_by("order")
        .values_list("entry__alias", flat=True)
    )


def _section_order(cv):
    from sections.models import CVSection

    return list(
        CVSection.objects.filter(cv=cv).order_by("order").values_list("section__title", flat=True)
    )


def test_drag_reorder_entries_and_sections_persists(app, page, cv, js_errors):
    app(f"/cv/{cv.id}/editor/")

    # Drag "charlie" above "alpha".
    page.locator("[aria-label='Drag to reorder charlie']").drag_to(
        page.locator("[aria-label='Drag to reorder alpha']")
    )
    page.wait_for_selector("text=Order saved")
    assert _entry_order("Achievements") == ["charlie", "alpha", "bravo"]

    # Drag the "Talks" section above "Achievements".
    page.locator("[aria-label='Drag to reorder section Talks']").drag_to(
        page.locator("[aria-label='Drag to reorder section Achievements']")
    )
    page.wait_for_function(
        "() => document.querySelectorAll('[aria-label^=\"Drag to reorder section\"]')[0]"
        ".getAttribute('aria-label').endsWith('Talks')"
    )
    page.wait_for_timeout(500)  # let the reorder POST land
    assert _section_order(cv) == ["Talks", "Achievements"]

    # A reload renders the persisted order.
    page.reload()
    labels = page.locator("[aria-label^='Drag to reorder section']").all_inner_texts()
    assert len(labels) == 2
    assert (
        page.locator("[aria-label^='Drag to reorder section']")
        .first.get_attribute("aria-label")
        .endswith("Talks")
    )
    assert js_errors == []


def test_translation_round_trip_updates_language_chip(app, page, cv, js_errors):
    app(f"/cv/{cv.id}/editor/")
    assert page.locator("button[title='0 of 4 entries translated']").count() == 0

    # Open "alpha" inline, add a Spanish translation.
    page.click("button:has-text('alpha')")
    panel = page.locator("[id^=inline-entry-]").first
    panel.locator("input[name=lang]").fill("es")
    panel.locator("button:has-text('+ Add')").click()
    page.wait_for_selector("text=EN (original)")
    panel.locator("[id^=translate-] [name=bullet]").fill("texto alfa")
    panel.locator("button:has-text('Save ES')").click()
    page.wait_for_selector("text=Saved ES translation.")

    from entries.models import BaseEntry

    alpha = BaseEntry.objects.select_subclasses().get(alias="alpha")
    assert alpha.translations == {"es": {"bullet": "texto alfa"}}

    # After a reload the ES chip shows 1 of 4 translated (partial dot).
    page.reload()
    chip = page.locator("button[title='1 of 4 entries translated']")
    assert chip.inner_text().strip().endswith("ES")
    assert "partially translated" in chip.inner_text()

    # Clicking the chip selects ES in the language picker.
    chip.click()
    assert page.input_value("select[name=language]") == "es"
    assert js_errors == []


def test_palette_enter_right_after_typing_waits_for_fresh_results(app, page, cv, js_errors):
    app("/")
    page.keyboard.press("Control+k")
    page.wait_for_selector("[role=option][aria-selected=true]")  # initial (empty-query) list
    page.locator("input[role=combobox]").press_sequentially("navy", delay=10)
    page.keyboard.press("Enter")  # before the debounced results arrive
    page.wait_for_url(re.compile(rf"/cv/{cv.id}/editor/$"))
    assert js_errors == []
