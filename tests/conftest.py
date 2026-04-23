"""Shared pytest fixtures.

We deliberately keep conftest thin — fixture logic lives in `tests/factories.py`
and gets surfaced here only when the fixture needs a particular name or scope.

`pytest-django` already provides `db`, `client`, `rf` (RequestFactory), and
`admin_client`. We add a few CVMaker-specific helpers on top.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from tests.factories import (
    BulletEntryFactory,
    CVFactory,
    EducationEntryFactory,
    ExperienceEntryFactory,
    SectionFactory,
    UserFactory,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
@pytest.fixture
def user(db):
    """A plain authenticated user. Email-identified per the custom User model."""
    return UserFactory()


@pytest.fixture
def other_user(db):
    """A second user, for ownership-boundary tests."""
    return UserFactory(email="other@example.com", username="other")


@pytest.fixture
def admin_user(db):
    """A superuser (email-identified)."""
    return UserFactory(
        email="admin@example.com",
        username="admin",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def authed_client(client, user):
    """A Django test client already logged in as `user`."""
    client.force_login(user)
    return client


@pytest.fixture
def admin_client(client, admin_user):
    """A Django test client already logged in as `admin_user`."""
    client.force_login(admin_user)
    return client


# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------
@pytest.fixture
def cv(db, user):
    """A CV owned by `user`."""
    return CVFactory(user=user)


@pytest.fixture
def section(db, user):
    """A Section owned by `user`."""
    return SectionFactory(user=user)


@pytest.fixture
def education_entry(db, user):
    return EducationEntryFactory(user=user)


@pytest.fixture
def experience_entry(db, user):
    return ExperienceEntryFactory(user=user)


@pytest.fixture
def bullet_entry(db, user):
    return BulletEntryFactory(user=user)
