"""SIGNUP_MODE=waitlist (Phase 6): collect emails instead of creating accounts.

With allauth, closing signup goes through ``AccountAdapter.is_open_for_signup``;
allauth then renders ``account/signup_closed.html``, which is our waitlist form.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from accounts.models import WaitlistEntry

pytestmark = pytest.mark.django_db
User = get_user_model()
PASSWORD = "Str0ng-pass-for-tests!"

waitlist = override_settings(SIGNUP_MODE="waitlist")


@waitlist
def test_signup_page_becomes_a_waitlist_form(client):
    body = client.get(reverse("account_signup")).content.decode()
    assert "Join the waitlist" in body
    assert f'action="{reverse("waitlist")}"' in body
    assert 'name="password1"' not in body


@waitlist
def test_joining_stores_the_email_normalised_and_toasts(client):
    resp = client.post(reverse("waitlist"), {"email": " Ada@Example.COM "}, follow=True)
    assert resp.redirect_chain[-1][0] == reverse("homepage")
    assert b"on the list" in resp.content
    assert list(WaitlistEntry.objects.values_list("email", flat=True)) == ["ada@example.com"]


@waitlist
def test_joining_twice_is_indistinguishable_and_not_duplicated(client):
    first = client.post(reverse("waitlist"), {"email": "ada@example.com"})
    second = client.post(reverse("waitlist"), {"email": "ADA@example.com"})
    assert first.status_code == second.status_code == 302
    assert WaitlistEntry.objects.count() == 1


@waitlist
def test_no_account_can_be_created_in_waitlist_mode(client):
    client.post(
        reverse("account_signup"),
        {"email": "sneaky@example.com", "password1": PASSWORD, "password2": PASSWORD},
    )
    assert not User.objects.filter(email="sneaky@example.com").exists()


@waitlist
def test_invalid_email_rerenders(client):
    resp = client.post(reverse("waitlist"), {"email": "not-an-email"})
    assert resp.status_code == 200 and b"text-danger" in resp.content
    assert not WaitlistEntry.objects.exists()


@waitlist
def test_nav_says_join_waitlist(client):
    assert b"Join waitlist" in client.get(reverse("homepage")).content


def test_open_mode_is_the_default_and_signup_still_works(client, settings):
    assert settings.SIGNUP_MODE == "open"
    assert b"Sign up" in client.get(reverse("homepage")).content
    client.post(
        reverse("account_signup"),
        {"email": "new@example.com", "password1": PASSWORD, "password2": PASSWORD},
    )
    assert User.objects.filter(email="new@example.com").exists()


def test_waitlist_url_redirects_to_signup_when_open(client):
    resp = client.get(reverse("waitlist"))
    assert resp.status_code == 302 and resp.url == reverse("account_signup")


def test_bad_signup_mode_fails_loudly(monkeypatch):
    import importlib

    from django.core.exceptions import ImproperlyConfigured

    import cvmaker.settings.base as base

    monkeypatch.setenv("SIGNUP_MODE", "closed")
    with pytest.raises(ImproperlyConfigured):
        importlib.reload(base)
    monkeypatch.delenv("SIGNUP_MODE")
    importlib.reload(base)  # leave the module as we found it
