"""Account Settings screen (``profile``): profile + password forms."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()
URL = reverse("profile")


def _profile(**overrides):
    data = {"action": "profile", "display_name": "", "email": "", "preferred_language": "en"}
    data.update(overrides)
    return data


def test_requires_login(client):
    resp = client.get(URL)
    assert resp.status_code == 302 and "login" in resp.url


def test_renders_both_forms(client, user):
    client.force_login(user)
    body = client.get(URL).content.decode()
    assert 'value="profile"' in body and 'value="password"' in body
    assert f'value="{user.email}"' in body
    assert 'name="old_password"' in body


def test_profile_saves_and_flashes(client, user):
    client.force_login(user)
    resp = client.post(
        URL,
        _profile(display_name="Ada", email="ada@example.com", preferred_language="pt_br"),
        follow=True,
    )
    user.refresh_from_db()
    assert (user.display_name, user.email, user.preferred_language) == (
        "Ada",
        "ada@example.com",
        "pt-BR",  # normalised
    )
    assert b'id="flash"' in resp.content and b"Profile saved." in resp.content


def test_email_taken_case_insensitively(client, user):
    UserFactory(email="taken@example.com", username="taken")
    client.force_login(user)
    resp = client.post(URL, _profile(email="TAKEN@example.com"))
    assert resp.status_code == 200
    assert b"Another account already uses this email" in resp.content
    user.refresh_from_db()
    assert user.email != "TAKEN@example.com"


def test_bad_language_rejected(client, user):
    client.force_login(user)
    resp = client.post(URL, _profile(email=user.email, preferred_language="eng"))
    assert b"Use a language code like" in resp.content


def test_password_change_keeps_session(client, user):
    user.set_password("old-pass-123!")
    user.save()
    client.force_login(user)

    resp = client.post(
        URL,
        {
            "action": "password",
            "old_password": "old-pass-123!",
            "new_password1": "brand-new-Pass-456",
            "new_password2": "brand-new-Pass-456",
        },
    )

    assert resp.status_code == 302
    user.refresh_from_db()
    assert user.check_password("brand-new-Pass-456")
    assert client.get(URL).status_code == 200  # still logged in


def test_wrong_old_password_rejected(client, user):
    client.force_login(user)
    resp = client.post(
        URL,
        {
            "action": "password",
            "old_password": "nope",
            "new_password1": "brand-new-Pass-456",
            "new_password2": "brand-new-Pass-456",
        },
    )
    assert resp.status_code == 200
    assert b"text-danger" in resp.content


def test_nav_links_to_settings_when_logged_in(client, user):
    client.force_login(user)
    assert f'href="{URL}"'.encode() in client.get(reverse("cv-list")).content
