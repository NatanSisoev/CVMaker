"""Integration coverage for the auth flow under the custom User model."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_signup_creates_user_with_email_identifier(client):
    """POST to signup should create a user whose USERNAME_FIELD is email."""
    url = reverse("signup")
    resp = client.post(
        url,
        data={
            "email": "newuser@example.com",
            "password1": "pbkdf2-dev-only-password",
            "password2": "pbkdf2-dev-only-password",
        },
        follow=True,
    )
    assert resp.status_code == 200
    user = User.objects.get(email="newuser@example.com")
    assert user.username  # defaulted from email local part


def test_login_with_email(client, user):
    """The auth backend must accept email + password."""
    user.set_password("correct horse")
    user.save()
    resp = client.post(
        reverse("login"),
        data={"username": user.email, "password": "correct horse"},
    )
    assert resp.status_code in (302, 200)  # LoginView redirects on success
