"""Quick-start CV creation and inline personal details in the editor."""

from __future__ import annotations

import json

import pytest
from django.urls import reverse

from cv.models import CV, CVInfo
from cv.services import create_starter_cv
from tests.factories import CVFactory

pytestmark = pytest.mark.django_db


def test_starter_cv_is_prefilled_from_the_account(user):
    user.display_name = "Ada L"
    user.save()
    cv = create_starter_cv(user, "  Data engineer  ")
    assert cv.alias == "Data engineer"
    assert (cv.info.name, cv.info.email) == ("Ada L", user.email)
    assert cv.design.theme == "classic"
    assert cv.user == cv.info.user == cv.design.user == user


def test_starter_alias_is_clamped_and_never_empty(user):
    assert len(create_starter_cv(user, "x" * 60).alias) == 20
    assert create_starter_cv(user, "   ").alias == "My CV"


def test_new_cv_page_and_entry_points(client, user):
    client.force_login(user)
    assert b"Name your CV" in client.get(reverse("cv-new")).content
    for name in ("cv-list", "homepage"):
        assert reverse("cv-new").encode() in client.get(reverse(name)).content


def test_posting_a_name_creates_the_cv_and_opens_the_editor(client, user):
    client.force_login(user)
    resp = client.post(reverse("cv-new"), {"alias": "Academic"}, follow=True)
    cv = CV.objects.get(user=user)
    assert resp.redirect_chain[-1][0] == reverse("cv-editor", args=[cv.id])
    assert b"Created Academic." in resp.content
    assert b"Personal details" in resp.content


def test_new_cv_validation_and_login(client, user):
    assert client.get(reverse("cv-new")).status_code == 302  # anonymous
    client.force_login(user)
    resp = client.post(reverse("cv-new"), {"alias": "y" * 21})
    assert resp.status_code == 200 and b"text-danger" in resp.content
    assert not CV.objects.exists()


def test_palette_new_cv_action_goes_to_quick_start(client, user):
    client.force_login(user)
    body = client.get(reverse("palette"), {"q": "new cv"}).content.decode()
    assert f'data-url="{reverse("cv-new")}"' in body


# ---------------------------------------------------------------------------
# Personal details, inline
# ---------------------------------------------------------------------------
@pytest.fixture
def nameless_user(user):
    """UserFactory fills display_name; the empty-name flows need it blank."""
    user.display_name = ""
    user.save()
    return user


def _url(cv):
    return reverse("cv-info-inline", kwargs={"cv_id": cv.id})


def test_editor_opens_details_while_the_name_is_empty(client, nameless_user):
    cv = create_starter_cv(nameless_user, "A")  # account has no display name -> empty name
    client.force_login(nameless_user)
    body = client.get(reverse("cv-editor", args=[cv.id])).content.decode()
    assert "open: true" in body and "Add your name" in body


def test_editor_collapses_details_once_named(client, user):
    cv = create_starter_cv(user, "A")
    cv.info.name = "Ada"
    cv.info.save()
    client.force_login(user)
    body = client.get(reverse("cv-editor", args=[cv.id])).content.decode()
    assert "open: false" in body and ">Ada<" in body


def test_get_returns_prefilled_fragment(client, user):
    cv = create_starter_cv(user, "A")
    client.force_login(user)
    body = client.get(_url(cv)).content.decode()
    assert f'value="{user.email}"' in body and "<html" not in body


def test_save_updates_the_record_toasts_and_refreshes_the_summary(client, user):
    cv = create_starter_cv(user, "A")
    client.force_login(user)

    resp = client.post(
        _url(cv),
        {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "",
            "location": "London",
            "website": "",
        },
    )

    assert resp.status_code == 200
    cv.info.refresh_from_db()
    assert (cv.info.name, cv.info.location) == ("Ada Lovelace", "London")
    assert json.loads(resp["HX-Trigger"])["toast"]["variant"] == "success"
    assert b'id="info-summary"' in resp.content and b'hx-swap-oob="true"' in resp.content
    assert CVInfo.objects.count() == 1  # edited in place


def test_save_creates_and_attaches_a_record_when_the_cv_has_none(client, user):
    cv = CVFactory(user=user, alias="bare")
    assert cv.info is None
    client.force_login(user)

    client.post(
        _url(cv), {"name": "Grace", "email": "", "phone": "", "location": "", "website": ""}
    )

    cv.refresh_from_db()
    assert cv.info.name == "Grace" and cv.info.user == user and cv.info.alias == "bare"


def test_invalid_details_rerender_with_errors_and_save_nothing(client, nameless_user):
    cv = create_starter_cv(nameless_user, "A")
    client.force_login(nameless_user)
    resp = client.post(_url(cv), {"name": "Ada", "email": "not-an-email"})
    assert resp.status_code == 200 and b"text-danger" in resp.content
    assert "HX-Trigger" not in resp
    cv.info.refresh_from_db()
    assert cv.info.name == ""


def test_other_users_cannot_touch_the_details(client, nameless_user, other_user):
    cv = create_starter_cv(nameless_user, "A")
    client.force_login(other_user)
    assert client.get(_url(cv)).status_code == 404
    assert client.post(_url(cv), {"name": "Mallory"}).status_code == 404
    cv.info.refresh_from_db()
    assert cv.info.name == ""


def test_starter_cv_renders_once_it_has_a_section(user):
    from cv.services import build_render_payload
    from rendering import tasks
    from sections.models import SectionEntry
    from sections.services import attach_section_to_cv
    from tests.factories import BulletEntryFactory, SectionFactory

    cv = create_starter_cv(user, "A")
    cv.info.name = "Ada"
    cv.info.save()
    section = SectionFactory(user=user, title="Highlights")
    SectionEntry.objects.create(section=section, entry=BulletEntryFactory(user=user), order=0)
    attach_section_to_cv(cv, section)
    assert tasks._render_payload_to_pdf(build_render_payload(cv)).startswith(b"%PDF")
