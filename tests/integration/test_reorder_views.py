"""Drag-reorder endpoints used by the Editor screen."""

from __future__ import annotations

import pytest
from django.urls import reverse

from sections.models import CVSection, SectionEntry
from tests.factories import BulletEntryFactory, SectionFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def cv_with_sections(cv):
    sections = [SectionFactory(user=cv.user) for _ in range(3)]
    for order, section in enumerate(sections):
        CVSection.objects.create(cv=cv, section=section, order=order)
    return cv, sections


@pytest.fixture
def section_with_entries(section):
    entries = [BulletEntryFactory(user=section.user) for _ in range(3)]
    for order, entry in enumerate(entries):
        SectionEntry.objects.create(section=section, entry=entry, order=order)
    return section, entries


def _post_ids(client, url, ids):
    return client.post(url, {"ids": [str(i) for i in ids]})


def _section_order(cv):
    return list(
        CVSection.objects.filter(cv=cv).order_by("order").values_list("section_id", flat=True)
    )


class TestReorderCvSections:
    def test_owner_reorders(self, client, cv_with_sections):
        cv, (a, b, c) = cv_with_sections
        client.force_login(cv.user)

        resp = _post_ids(client, reverse("cv-reorder-sections", args=[cv.id]), [c.id, a.id, b.id])

        assert resp.status_code == 204
        assert _section_order(cv) == [c.id, a.id, b.id]

    def test_section_not_in_cv_is_400_and_rolls_back(self, client, cv_with_sections):
        cv, (a, b, c) = cv_with_sections
        stranger = SectionFactory(user=cv.user)
        client.force_login(cv.user)

        resp = _post_ids(client, reverse("cv-reorder-sections", args=[cv.id]), [c.id, stranger.id])

        assert resp.status_code == 400
        assert _section_order(cv) == [a.id, b.id, c.id]  # the first write was rolled back

    def test_garbage_id_is_400(self, client, cv_with_sections):
        cv, _ = cv_with_sections
        client.force_login(cv.user)
        resp = client.post(reverse("cv-reorder-sections", args=[cv.id]), {"ids": ["nope"]})
        assert resp.status_code == 400

    def test_empty_is_400(self, client, cv_with_sections):
        cv, _ = cv_with_sections
        client.force_login(cv.user)
        assert client.post(reverse("cv-reorder-sections", args=[cv.id])).status_code == 400

    def test_non_owner_is_404(self, client, cv_with_sections, other_user):
        cv, sections = cv_with_sections
        client.force_login(other_user)
        url = reverse("cv-reorder-sections", args=[cv.id])
        assert _post_ids(client, url, [s.id for s in sections]).status_code == 404

    def test_get_not_allowed(self, client, cv_with_sections):
        cv, _ = cv_with_sections
        client.force_login(cv.user)
        assert client.get(reverse("cv-reorder-sections", args=[cv.id])).status_code == 405

    def test_anonymous_redirected(self, client, cv_with_sections):
        cv, _ = cv_with_sections
        assert client.post(reverse("cv-reorder-sections", args=[cv.id])).status_code == 302


class TestReorderSectionEntries:
    def test_owner_reorders(self, client, section_with_entries):
        section, (a, b, c) = section_with_entries
        client.force_login(section.user)

        url = reverse("section-reorder-entries", args=[section.id])
        resp = _post_ids(client, url, [b.id, c.id, a.id])

        assert resp.status_code == 204
        ordered = section.section_entries.order_by("order").values_list("entry_id", flat=True)
        assert list(ordered) == [b.id, c.id, a.id]

    def test_entry_not_in_section_is_400(self, client, section_with_entries):
        section, (a, _, _) = section_with_entries
        outsider = BulletEntryFactory(user=section.user)
        client.force_login(section.user)
        url = reverse("section-reorder-entries", args=[section.id])
        assert _post_ids(client, url, [outsider.id, a.id]).status_code == 400

    def test_non_owner_is_404(self, client, section_with_entries, other_user):
        section, entries = section_with_entries
        client.force_login(other_user)
        url = reverse("section-reorder-entries", args=[section.id])
        assert _post_ids(client, url, [e.id for e in entries]).status_code == 404


def test_editor_wires_sortable_lists(client, cv_with_sections):
    cv, sections = cv_with_sections
    client.force_login(cv.user)
    body = client.get(reverse("cv-editor", args=[cv.id])).content.decode()

    assert f'x-sortable="{reverse("cv-reorder-sections", args=[cv.id])}"' in body
    assert body.count("data-drag-handle") >= len(sections)
    # Sections render in CVSection order.
    positions = [body.index(f'data-id="{s.id}"') for s in sections]
    assert positions == sorted(positions)
