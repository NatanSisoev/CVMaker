"""Unit tests for the Phase 2.3 service layer.

Coverage targets:

  - ``cv.services.build_render_payload`` -- language threading,
    side-effect-free overrides.
  - ``cv.services.clone_cv`` -- per-CV singletons get duplicated, sections
    are shared, ordering is preserved.
  - ``sections.services.reorder_sections`` and ``reorder_entries`` --
    the CVSection / SectionEntry order columns get rewritten exactly.
  - ``sections.services.import_sections_from_data_model`` -- happy-path
    walk over a synthetic data model.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cv.models import CVInfo
from cv.services import build_render_payload, clone_cv
from sections.models import CVSection, SectionEntry
from sections.services import (
    import_sections_from_data_model,
    reorder_entries,
    reorder_sections,
)
from tests.factories import (
    CVFactory,
    EducationEntryFactory,
    SectionFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# build_render_payload
# ---------------------------------------------------------------------------
class TestBuildRenderPayload:
    def test_returns_dict_with_top_level_keys(self):
        cv = CVFactory()
        payload = build_render_payload(cv)
        assert set(payload.keys()) == {"cv", "design", "locale", "rendercv_settings"}

    def test_language_override_is_side_effect_free(self):
        """Calling build_render_payload with a different language must not
        mutate the persisted CVLocale.language."""
        from cv.models import CVLocale

        user = UserFactory()
        locale = CVLocale.objects.create(user=user, language="en")
        cv = CVFactory(user=user, locale=locale)

        # Ad-hoc render in Spanish.
        build_render_payload(cv, language="es")

        # Reload from the DB -- language should still be "en".
        locale.refresh_from_db()
        assert locale.language == "en"


# ---------------------------------------------------------------------------
# clone_cv
# ---------------------------------------------------------------------------
class TestCloneCv:
    def test_alias_set_on_clone(self):
        cv = CVFactory(alias="original")
        clone = clone_cv(cv, new_alias="copy")
        assert clone.alias == "copy"
        assert clone.user_id == cv.user_id

    def test_new_pk(self):
        cv = CVFactory()
        clone = clone_cv(cv, new_alias="copy")
        assert clone.pk != cv.pk

    def test_singletons_are_copied_not_shared(self):
        user = UserFactory()
        info = CVInfo.objects.create(user=user, name="Original Person")
        cv = CVFactory(user=user, info=info)

        clone = clone_cv(cv, new_alias="copy")

        # Different rows.
        assert clone.info_id != cv.info_id
        # Same data.
        assert clone.info.name == "Original Person"

        # Edit the clone's info; original stays put.
        clone.info.name = "Edited"
        clone.info.save()
        cv.refresh_from_db()
        assert cv.info.name == "Original Person"

    def test_sections_are_shared(self):
        user = UserFactory()
        section = SectionFactory(user=user, title="Education")
        cv = CVFactory(user=user)
        CVSection.objects.create(cv=cv, section=section, order=1)

        clone = clone_cv(cv, new_alias="copy")

        # CVSection rows are recreated, but the underlying Section is the
        # same row.
        clone_links = list(CVSection.objects.filter(cv=clone))
        assert len(clone_links) == 1
        assert clone_links[0].section_id == section.pk

    def test_section_order_preserved(self):
        user = UserFactory()
        sections = [SectionFactory(user=user, title=f"Section {i}") for i in range(3)]
        cv = CVFactory(user=user)
        for i, sec in enumerate(sections):
            CVSection.objects.create(cv=cv, section=sec, order=i)

        clone = clone_cv(cv, new_alias="copy")

        clone_links = CVSection.objects.filter(cv=clone).order_by("order")
        original_links = CVSection.objects.filter(cv=cv).order_by("order")
        assert [c.section_id for c in clone_links] == [o.section_id for o in original_links]


# ---------------------------------------------------------------------------
# reorder_sections
# ---------------------------------------------------------------------------
class TestReorderSections:
    def test_rewrites_order_to_match_input(self):
        user = UserFactory()
        cv = CVFactory(user=user)
        sections = [SectionFactory(user=user) for _ in range(3)]
        for i, sec in enumerate(sections):
            CVSection.objects.create(cv=cv, section=sec, order=i)

        # Reverse order: pass section UUIDs in reverse.
        reorder_sections(cv, [sections[2].id, sections[0].id, sections[1].id])

        result = list(
            CVSection.objects.filter(cv=cv).order_by("order").values_list("section_id", flat=True)
        )
        assert result == [sections[2].id, sections[0].id, sections[1].id]

    def test_unknown_section_raises(self):
        cv = CVFactory()
        with pytest.raises(CVSection.DoesNotExist):
            reorder_sections(cv, ["00000000-0000-0000-0000-000000000000"])


# ---------------------------------------------------------------------------
# reorder_entries
# ---------------------------------------------------------------------------
class TestReorderEntries:
    def test_rewrites_entry_order(self):
        user = UserFactory()
        section = SectionFactory(user=user)
        entries = [EducationEntryFactory(user=user) for _ in range(3)]
        for i, e in enumerate(entries):
            SectionEntry.objects.create(section=section, entry=e, order=i)

        reorder_entries(section, [entries[2].id, entries[0].id, entries[1].id])

        ordered = list(
            SectionEntry.objects.filter(section=section)
            .order_by("order")
            .values_list("entry_id", flat=True)
        )
        assert ordered == [entries[2].id, entries[0].id, entries[1].id]


# ---------------------------------------------------------------------------
# import_sections_from_data_model
# ---------------------------------------------------------------------------
class TestImportSectionsFromDataModel:
    """Spot-check the happy path. The full integration with rendercv's
    real data model is exercised in the YAML import view tests (Phase
    1.6 e2e / Phase 3 once the renderer ships)."""

    def test_skips_when_no_sections_attribute(self):
        user = UserFactory()
        cv = CVFactory(user=user)
        # Data model whose .cv has no .sections attribute.
        data_model = SimpleNamespace(cv=SimpleNamespace())
        import_sections_from_data_model(user, cv, data_model, alias="test")
        assert not CVSection.objects.filter(cv=cv).exists()

    def test_creates_sections_with_entries(self):
        user = UserFactory()
        cv = CVFactory(user=user)
        # Synthesize a minimal data model with one BulletEntry section.
        bullet_data = SimpleNamespace(dict=lambda: {"bullet": "Imported bullet."})
        section_data = SimpleNamespace(
            title="Highlights",
            entry_type="BulletEntry",
            entries=[bullet_data],
        )
        data_model = SimpleNamespace(cv=SimpleNamespace(sections=[section_data]))

        import_sections_from_data_model(user, cv, data_model, alias="imported")

        cv_links = list(CVSection.objects.filter(cv=cv))
        assert len(cv_links) == 1
        section = cv_links[0].section
        assert section.title == "Highlights"
        assert section.alias == "imported"
        # One SectionEntry pointing at one BulletEntry.
        section_entries = list(SectionEntry.objects.filter(section=section))
        assert len(section_entries) == 1
        bullet = section_entries[0].real_entry
        assert bullet.bullet == "Imported bullet."
