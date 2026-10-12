"""Opt-in public profile pages."""

from __future__ import annotations

import pytest
from django.urls import reverse

from accounts.public import present_entry
from cv.models import CVInfo
from sections.services import append_entry_to_section, attach_section_to_cv
from tests.factories import (
    BulletEntryFactory,
    CVFactory,
    EducationEntryFactory,
    SectionFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def published(user):
    info = CVInfo.objects.create(
        user=user,
        alias="me",
        name="Grace Hopper",
        email="grace@navy.mil",
        phone="555-0100",
        location="Arlington",
    )
    cv = CVFactory(user=user, info=info)
    section = SectionFactory(user=user, title="Achievements")
    append_entry_to_section(section, BulletEntryFactory(user=user, bullet="Found the first bug"))
    attach_section_to_cv(cv, section)
    user.public_handle, user.public_cv = "grace", cv
    user.save()
    return user


def test_public_page_renders_name_sections_and_hides_contact(client, published):
    resp = client.get("/@grace/")
    body = resp.content.decode()
    assert resp.status_code == 200
    assert "Grace Hopper" in body and "Achievements" in body and "Found the first bug" in body
    assert "grace@navy.mil" not in body and "555-0100" not in body


def test_contact_shown_only_when_opted_in(client, published):
    published.public_show_contact = True
    published.save()
    body = client.get("/@grace/").content.decode()
    assert "grace@navy.mil" in body and "555-0100" in body


def test_handle_is_case_insensitive_and_unknown_or_private_is_404(client, published, user):
    assert client.get("/@GRACE/").status_code == 200
    assert client.get("/@nobody/").status_code == 404
    published.public_cv = None
    published.save()
    assert client.get("/@grace/").status_code == 404


def test_page_is_html_escaped(client, published):
    published.public_cv.info.name = "<script>alert(1)</script>"
    published.public_cv.info.save()
    assert "<script>alert(1)" not in client.get("/@grace/").content.decode()


def test_settings_form_validates_handle_and_cv_ownership(client, published, other_user):
    client.force_login(published)
    base = {"display_name": "", "preferred_language": "en"}
    theirs = CVFactory(user=other_user)

    def post(**extra):
        return client.post(reverse("profile"), {"action": "profile", **base, **extra})

    assert (
        post(public_handle="ab", public_cv=published.public_cv_id).status_code == 200
    )  # too short
    assert post(public_handle="bad handle", public_cv=published.public_cv_id).status_code == 200
    assert post(public_handle="grace2", public_cv=theirs.id).status_code == 200  # not their CV
    assert post(public_handle="grace2").status_code == 200  # handle without a CV
    ok = post(public_handle="Grace2", public_cv=published.public_cv_id)
    assert ok.status_code == 302
    published.refresh_from_db()
    assert published.public_handle == "grace2"


def test_handles_are_unique_and_empty_means_private(client, published):
    other = UserFactory()
    other_cv = CVFactory(user=other)
    client.force_login(other)
    data = {"action": "profile", "preferred_language": "en", "display_name": ""}
    assert (
        client.post(
            reverse("profile"), {**data, "public_handle": "grace", "public_cv": other_cv.id}
        ).status_code
        == 200
    )
    assert client.post(reverse("profile"), {**data, "public_handle": ""}).status_code == 302
    other.refresh_from_db()
    assert other.public_handle is None


def test_present_entry_shapes():
    assert present_entry("plain")["bullets"] == ["plain"]
    shaped = present_entry(
        {"company": "ACME", "position": "Dev", "start_date": "2020", "highlights": ["Did x"]}
    )
    assert (
        shaped["headline"] == "Dev" and "ACME" in shaped["sub"] and shaped["bullets"] == ["Did x"]
    )
    assert "2020 - present" in shaped["sub"]


def test_education_entries_present(client, published):
    section = SectionFactory(user=published, title="School")
    append_entry_to_section(section, EducationEntryFactory(user=published))
    attach_section_to_cv(published.public_cv, section)
    assert "School" in client.get("/@grace/").content.decode()


def test_social_metadata_present_and_json_ld_is_safe(client, published):
    published.public_cv.info.name = "</script><b>x"
    published.public_cv.info.save()
    body = client.get("/@grace/").content.decode()
    assert 'property="og:title"' in body and 'id="ld-person"' in body
    assert "</script><b>" not in body
