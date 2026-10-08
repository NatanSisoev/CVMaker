"""GDPR (Phase 6): data export and hard account deletion."""

from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.urls import reverse
from rest_framework.authtoken.models import Token

from cv.models import CV, CVInfo
from entries.models import BaseEntry
from rendering.models import Render, RenderStatus
from sections.models import CVSection, Section, SectionEntry
from tests.factories import BulletEntryFactory, CVFactory, SectionFactory

pytestmark = pytest.mark.django_db
User = get_user_model()
PASSWORD = "Correct-Horse-1234"


@pytest.fixture
def owner(user):
    user.set_password(PASSWORD)
    user.save()
    return user


@pytest.fixture
def owned_data(owner):
    info = CVInfo.objects.create(user=owner, alias="me", name="Ada")
    cv = CVFactory(user=owner, alias="mine", info=info)
    section = SectionFactory(user=owner, title="Highlights")
    entry = BulletEntryFactory(
        user=owner, alias="algo", bullet="First algorithm", translations={"es": {"bullet": "Uno"}}
    )
    SectionEntry.objects.create(section=section, entry=entry, order=0)
    CVSection.objects.create(cv=cv, section=section, order=0)
    render = Render.objects.create(
        cv=cv, language="", style="", payload_hash="h", status=RenderStatus.DONE
    )
    render.pdf_file.save("mine.pdf", ContentFile(b"%PDF-1.4 owned"), save=True)
    return {"cv": cv, "entry": entry, "render": render}


@pytest.fixture
def someone_else(other_user):
    cv = CVFactory(user=other_user, alias="theirs")
    BulletEntryFactory(user=other_user, alias="their-entry")
    return cv


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def test_export_requires_login(client):
    resp = client.get(reverse("account-export"))
    assert resp.status_code == 302 and "login" in resp.url


def test_export_contains_your_data_and_nothing_else(client, owner, owned_data, someone_else):
    from allauth.account.models import EmailAddress

    EmailAddress.objects.create(user=owner, email=owner.email, verified=True, primary=True)
    Token.objects.create(user=owner)
    client.force_login(owner)

    resp = client.get(reverse("account-export"))

    assert resp.status_code == 200
    assert resp["Content-Disposition"].startswith('attachment; filename="cvmaker-export-')
    data = json.loads(resp.content)
    assert data["format"] == "cvmaker-export" and data["version"] == 1
    assert data["account"]["email"] == owner.email
    assert data["account"]["email_addresses"] == [
        {"email": owner.email, "verified": True, "primary": True}
    ]
    assert [c["alias"] for c in data["cvs"]] == ["mine"]
    (entry,) = data["entries"]
    assert entry["alias"] == "algo" and entry["type"] == "bullet"
    assert entry["translations"] == {"es": {"bullet": "Uno"}}
    assert data["sections"][0]["entries"] == [entry["id"]]
    assert data["cvs"][0]["sections"] == [data["sections"][0]["id"]]
    assert data["renders"][0]["pdf_file"].endswith(".pdf")

    raw = resp.content.decode()
    assert "theirs" not in raw and "their-entry" not in raw
    assert "pbkdf2" not in raw and "password" not in raw  # no hash leaks
    assert Token.objects.get(user=owner).key not in raw


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------
def _delete(client, password=PASSWORD, email=None, user=None):
    return client.post(
        reverse("profile"),
        {"action": "delete-account", "password": password, "confirm_email": email or user.email},
    )


@pytest.mark.parametrize(
    ("password", "email", "error"),
    [
        ("wrong-password", None, b"That password is not correct."),
        (PASSWORD, "someone@else.com", b"match your account"),
    ],
)
def test_delete_refused_without_password_and_matching_email(
    client, owner, owned_data, password, email, error
):
    client.force_login(owner)
    resp = _delete(client, password, email, user=owner)
    assert resp.status_code == 200 and error in resp.content
    assert User.objects.filter(pk=owner.pk).exists()


def test_delete_removes_everything_including_files_and_logs_out(
    client, owner, owned_data, someone_else
):
    token = Token.objects.create(user=owner).key
    pdf = owned_data["render"].pdf_file
    storage, pdf_name = pdf.storage, pdf.name
    assert storage.exists(pdf_name)
    client.force_login(owner)

    resp = _delete(client, email=owner.email.upper(), user=owner)  # case-insensitive confirm

    assert resp.status_code == 302 and resp.url == reverse("homepage")
    assert not User.objects.filter(pk=owner.pk).exists()
    for model in (CV, CVInfo, Section, BaseEntry, Render, Token):
        assert not model.objects.filter(
            **({"cv__user_id": owner.pk} if model is Render else {"user_id": owner.pk})
        ).exists(), model.__name__
    assert not storage.exists(pdf_name)  # files don't cascade; deleted explicitly

    # Logged out, and the old API token is dead.
    assert client.get(reverse("cv-list")).status_code == 302
    from rest_framework.test import APIClient

    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Token {token}")
    assert api.get(reverse("api:cv-list")).status_code == 401

    # Other users are untouched.
    assert CV.objects.filter(pk=someone_else.pk).exists()
    assert BaseEntry.objects.filter(alias="their-entry").exists()


def test_delete_survives_a_missing_file(client, owner, owned_data):
    pdf = owned_data["render"].pdf_file
    pdf.storage.delete(pdf.name)  # file already gone
    client.force_login(owner)
    assert _delete(client, user=owner).status_code == 302
    assert not User.objects.filter(pk=owner.pk).exists()
