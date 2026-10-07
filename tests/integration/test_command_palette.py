"""Command palette (``palette``): results fragment + page wiring."""

from __future__ import annotations

import pytest
from django.urls import reverse

from tests.factories import BulletEntryFactory, CVFactory, SectionFactory

pytestmark = pytest.mark.django_db
URL = reverse("palette")


def _options(resp):
    return resp.content.decode().count('role="option"')


def test_requires_login(client):
    resp = client.get(URL)
    assert resp.status_code == 302 and "login" in resp.url


def test_empty_query_lists_actions_and_recent_cvs(client, user):
    cv = CVFactory(user=user, alias="research-cv")
    client.force_login(user)

    body = client.get(URL).content.decode()

    assert "New CV" in body and "Settings" in body
    assert "research-cv" in body
    assert f'data-url="{reverse("cv-editor", args=[cv.id])}"' in body
    assert "<html" not in body  # fragment


def test_query_searches_every_group_case_insensitively(client, user):
    CVFactory(user=user, alias="Thesis CV")
    SectionFactory(user=user, title="Thesis work")
    entry = BulletEntryFactory(user=user, alias="thesis-defence")
    CVFactory(user=user, alias="unrelated")
    client.force_login(user)

    body = client.get(URL, {"q": "THESIS"}).content.decode()

    assert "Thesis CV" in body and "Thesis work" in body and "thesis-defence" in body
    assert "unrelated" not in body
    assert f'data-url="{reverse("entry-detail", kwargs={"entry_id": entry.id})}"' in body
    assert ">Bullet<" in body  # entry kind hint


def test_actions_filtered_by_query(client, user):
    client.force_login(user)
    body = client.get(URL, {"q": "sett"}).content.decode()
    assert "Settings" in body and "New CV" not in body


def test_only_own_data_is_searched(client, user, other_user):
    CVFactory(user=other_user, alias="secret-cv")
    BulletEntryFactory(user=other_user, alias="secret-entry")
    client.force_login(user)
    resp = client.get(URL, {"q": "secret"})
    assert _options(resp) == 0
    assert "No matches" in resp.content.decode()


def test_groups_are_capped(client, user):
    for i in range(8):
        CVFactory(user=user, alias=f"cv-{i}")
    client.force_login(user)
    body = client.get(URL, {"q": "cv-"}).content.decode()
    assert sum(f"cv-{i}<" in body for i in range(8)) == 5


def test_palette_mounted_only_for_logged_in_users(client, user):
    assert b'x-data="palette"' not in client.get(reverse("homepage")).content
    client.force_login(user)
    body = client.get(reverse("homepage")).content.decode()
    assert 'x-data="palette"' in body
    assert f'hx-get="{URL}"' in body
    assert "open-palette" in body  # nav trigger
