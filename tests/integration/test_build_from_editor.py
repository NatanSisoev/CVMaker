"""Building a CV from inside the editor: + Add section, + New entry."""

from __future__ import annotations

import pytest
from django.urls import reverse

from sections.models import CVSection, Section, SectionEntry
from sections.services import (
    append_entry_to_section,
    attach_section_to_cv,
    section_entry_kind,
)
from tests.factories import (
    BulletEntryFactory,
    CVFactory,
    EducationEntryFactory,
    SectionFactory,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Service helpers
# ---------------------------------------------------------------------------
def test_attach_section_appends_after_the_last_and_is_idempotent(cv, user):
    a, b = SectionFactory(user=user), SectionFactory(user=user)
    attach_section_to_cv(cv, a)
    attach_section_to_cv(cv, b)
    attach_section_to_cv(cv, a)  # again: no duplicate, order unchanged
    rows = list(
        CVSection.objects.filter(cv=cv).order_by("order").values_list("section_id", "order")
    )
    assert rows == [(a.id, 0), (b.id, 1)]


def test_append_entry_goes_to_the_end(section, user):
    first, second = BulletEntryFactory(user=user), BulletEntryFactory(user=user)
    SectionEntry.objects.create(section=section, entry=first, order=7)
    append_entry_to_section(section, second)
    assert list(section.section_entries.order_by("order").values_list("entry_id", flat=True)) == [
        first.id,
        second.id,
    ]


def test_section_entry_kind(section, user):
    assert section_entry_kind(section) is None
    append_entry_to_section(section, EducationEntryFactory(user=user))
    assert section_entry_kind(section) == "education"


# ---------------------------------------------------------------------------
# + Add section
# ---------------------------------------------------------------------------
def test_editor_offers_add_section_and_new_entry(client, user, cv, section):
    attach_section_to_cv(cv, section)
    client.force_login(user)
    body = client.get(reverse("cv-editor", args=[cv.id])).content.decode()
    assert f"{reverse('section-create')}?cv={cv.id}" in body
    assert f"{reverse('entry-create')}?section={section.id}&amp;cv={cv.id}" in body or (
        f"{reverse('entry-create')}?section={section.id}&cv={cv.id}" in body
    )


def test_empty_editor_explains_what_a_section_is(client, user, cv):
    client.force_login(user)
    body = client.get(reverse("cv-editor", args=[cv.id])).content.decode()
    assert "no sections yet" in body and "+ Add section" in body


def test_new_section_from_the_editor_attaches_and_returns(client, user, cv):
    client.force_login(user)
    url = f"{reverse('section-create')}?cv={cv.id}"
    assert b"will be added to" in client.get(url).content

    resp = client.post(url, {"title": "Projects", "alias": "projects"})

    assert resp.status_code == 302 and resp.url == reverse("cv-editor", args=[cv.id])
    section = Section.objects.get(title="Projects")
    assert CVSection.objects.filter(cv=cv, section=section, order=0).exists()


def test_section_create_without_cv_is_unchanged(client, user):
    client.force_login(user)
    resp = client.post(reverse("section-create"), {"title": "Loose", "alias": "loose"})
    assert resp.url == reverse("section-list")
    assert not CVSection.objects.exists()


@pytest.mark.parametrize("bad", ["not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_bogus_cv_param_is_ignored(client, user, bad):
    client.force_login(user)
    resp = client.post(f"{reverse('section-create')}?cv={bad}", {"title": "T", "alias": "t"})
    assert resp.url == reverse("section-list")


def test_cannot_attach_to_someone_elses_cv(client, user, other_user):
    theirs = CVFactory(user=other_user)
    client.force_login(user)
    resp = client.post(f"{reverse('section-create')}?cv={theirs.id}", {"title": "T", "alias": "t"})
    assert resp.url == reverse("section-list")
    assert not CVSection.objects.filter(cv=theirs).exists()


# ---------------------------------------------------------------------------
# + New entry
# ---------------------------------------------------------------------------
def _entry_url(section, cv, **extra):
    query = f"section={section.id}&cv={cv.id}" + "".join(f"&{k}={v}" for k, v in extra.items())
    return f"{reverse('entry-create')}?{query}"


def test_empty_section_lets_you_pick_the_kind_and_keeps_context(client, user, cv, section):
    client.force_login(user)
    body = client.get(_entry_url(section, cv)).content.decode()
    assert f"Add an entry to {section.title}" in body
    assert f'name="section" value="{section.id}"' in body  # survives the GET kind picker
    assert f'name="cv" value="{cv.id}"' in body


def test_new_entry_is_appended_and_returns_to_the_editor(client, user, cv, section):
    client.force_login(user)
    url = _entry_url(section, cv, entry_type="bullet")

    resp = client.post(url, {"entry_type": "bullet", "alias": "shipped", "bullet": "Shipped it"})

    assert resp.status_code == 302 and resp.url == reverse("cv-editor", args=[cv.id])
    assert section_entry_kind(section) == "bullet"
    assert section.section_entries.get().entry.alias == "shipped"


def test_section_with_entries_locks_the_kind(client, user, cv, section):
    append_entry_to_section(section, EducationEntryFactory(user=user))
    client.force_login(user)

    page = client.get(_entry_url(section, cv)).content.decode()
    assert (
        "holds <strong>education</strong>" in page and 'name="institution"' in page
    )  # form, not picker

    # Tampering: posting another kind is refused and nothing is saved.
    from entries.models import BaseEntry

    before = BaseEntry.objects.count()
    resp = client.post(
        _entry_url(section, cv, entry_type="bullet"),
        {"entry_type": "bullet", "alias": "sneaky", "bullet": "x"},
    )
    assert resp.status_code == 302 and resp.url == reverse("cv-editor", args=[cv.id])
    assert BaseEntry.objects.count() == before


def test_invalid_entry_rerenders_with_context(client, user, cv, section):
    client.force_login(user)
    resp = client.post(
        _entry_url(section, cv, entry_type="bullet"), {"entry_type": "bullet", "alias": ""}
    )
    assert resp.status_code == 200 and f"Add an entry to {section.title}" in resp.content.decode()
    assert not section.section_entries.exists()


def test_entry_create_without_a_section_keeps_working(client, user):
    client.force_login(user)
    resp = client.post(
        reverse("entry-create"), {"entry_type": "bullet", "alias": "free", "bullet": "Standalone"}
    )
    assert resp.status_code == 302 and resp.url == reverse("entry-create")


def test_someone_elses_section_is_ignored(client, user, other_user):
    theirs = SectionFactory(user=other_user)
    client.force_login(user)
    body = client.get(f"{reverse('entry-create')}?section={theirs.id}").content.decode()
    assert "Create New Entry" in body and theirs.title not in body


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
def test_nav_links_the_library_for_signed_in_users(client, user):
    client.force_login(user)
    body = client.get(reverse("cv-list")).content.decode()
    assert f'href="{reverse("section-list")}"' in body and f'href="{reverse("entry-list")}"' in body


# ---------------------------------------------------------------------------
# Library pages: friendly kind names and usage
# ---------------------------------------------------------------------------
def test_entries_list_shows_friendly_kinds_and_usage(client, user, section):
    used = BulletEntryFactory(user=user, alias="used-one")
    BulletEntryFactory(user=user, alias="orphan")
    append_entry_to_section(section, used)
    client.force_login(user)

    body = client.get(reverse("entry-list")).content.decode()

    assert "BulletEntry" not in body and "Bullet ·" in body
    assert "used in 1 section" in body
    assert "not in any section yet" in body  # exactly the orphan
    assert body.count("not in any section yet") == 1


def test_sections_pages_use_friendly_kind_names(client, user, section):
    append_entry_to_section(section, EducationEntryFactory(user=user))
    client.force_login(user)
    for url in (reverse("section-list"), reverse("section-detail", args=[section.id])):
        body = client.get(url).content.decode()
        assert "Education" in body and "EducationEntry" not in body, url


def test_entries_list_search_and_unused_filter(client, user, section):
    append_entry_to_section(section, BulletEntryFactory(user=user, alias="alpha-used"))
    BulletEntryFactory(user=user, alias="alpha-loose")
    BulletEntryFactory(user=user, alias="beta-loose")
    BulletEntryFactory(alias="alpha-someone-elses")
    client.force_login(user)
    url = reverse("entry-list")

    def aliases(query=""):
        body = client.get(url + query).content.decode()
        return {
            a
            for a in ("alpha-used", "alpha-loose", "beta-loose", "alpha-someone-elses")
            if a in body
        }

    assert aliases() == {"alpha-used", "alpha-loose", "beta-loose"}
    assert aliases("?q=ALPHA") == {"alpha-used", "alpha-loose"}
    assert aliases("?unused=1") == {"alpha-loose", "beta-loose"}
    assert aliases("?q=alpha&unused=1") == {"alpha-loose"}
    assert "No entries match" in client.get(url + "?q=zzz").content.decode()
