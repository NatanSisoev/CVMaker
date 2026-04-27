"""Fast, migration-free tests for the custom User model."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_email_is_username_field():
    assert User.USERNAME_FIELD == "email"


def test_email_is_required_and_unique():
    email_field = User._meta.get_field("email")
    assert email_field.unique is True
    assert email_field.blank is False


def test_create_user_sets_usable_password():
    user = User.objects.create_user(
        email="alice@example.com",
        username="alice",
        password="correct horse battery staple",
    )
    assert user.has_usable_password()
    assert user.check_password("correct horse battery staple")


def test_create_user_rejects_missing_email():
    with pytest.raises(ValueError, match="email"):
        User.objects.create_user(email="", username="nobody", password="x")


def test_create_superuser_flags():
    admin = User.objects.create_superuser(
        email="admin@example.com",
        username="admin",
        password="x",
    )
    assert admin.is_staff
    assert admin.is_superuser
    assert admin.is_active


def test_email_normalized_to_domain_lowercase():
    user = User.objects.create_user(email="Alice@Example.COM", username="alice", password="x")
    # BaseUserManager.normalize_email lowercases the domain, not the local part.
    assert user.email.endswith("@example.com")


def test_default_preferred_language_is_en():
    user = User.objects.create_user(email="a@b.com", username="a", password="x")
    assert user.preferred_language == "en"
