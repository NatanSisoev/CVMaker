"""Account Settings screen (``profile``): profile + password forms."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

pytestmark = pytest.mark.django_db

User = get_user_model()
URL = reverse("profile")


def _profile(**overrides):
    data = {"action": "profile", "display_name": "", "preferred_language": "en"}
    data.update(overrides)
    return data


def test_requires_login(client):
    resp = client.get(URL)
    assert resp.status_code == 302 and "login" in resp.url


def test_renders_both_forms(client, user):
    client.force_login(user)
    body = client.get(URL).content.decode()
    assert 'value="profile"' in body and 'value="password"' in body
    assert user.email in body  # shown read-only; changed via allauth
    assert reverse("account_email") in body and reverse("mfa_index") in body
    assert 'name="old_password"' in body


def test_profile_saves_and_flashes(client, user):
    client.force_login(user)
    resp = client.post(
        URL,
        _profile(display_name="Ada", preferred_language="pt_br"),
        follow=True,
    )
    user.refresh_from_db()
    assert (user.display_name, user.preferred_language) == ("Ada", "pt-BR")  # normalised
    assert b'id="flash"' in resp.content and b"Profile saved." in resp.content


def test_profile_form_cannot_change_email(client, user):
    """Email changes must go through allauth so the new address is verified."""
    client.force_login(user)
    original = user.email
    client.post(URL, {**_profile(display_name="X"), "email": "hijack@example.com"})
    user.refresh_from_db()
    assert user.email == original


def test_bad_language_rejected(client, user):
    client.force_login(user)
    resp = client.post(URL, _profile(preferred_language="eng"))
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
