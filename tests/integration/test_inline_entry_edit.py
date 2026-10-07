"""Inline entry editing inside the Editor screen (HTMX fragment)."""

from __future__ import annotations

import json

import pytest
from django.urls import reverse

from tests.factories import BulletEntryFactory, ExperienceEntryFactory

pytestmark = pytest.mark.django_db


def test_get_returns_prefilled_fragment(client, user):
    entry = ExperienceEntryFactory(user=user, company="Acme")
    client.force_login(user)

    resp = client.get(reverse("entry-inline", kwargs={"entry_id": entry.id}))

    assert resp.status_code == 200
    body = resp.content.decode()
    assert f'id="inline-entry-{entry.id}"' in body
    assert 'value="Acme"' in body
    assert "<html" not in body  # a fragment, not a full page


def test_valid_post_saves_and_fires_toast(client, user):
    entry = BulletEntryFactory(user=user, bullet="old")
    client.force_login(user)

    resp = client.post(
        reverse("entry-inline", kwargs={"entry_id": entry.id}),
        {"alias": entry.alias, "bullet": "new text"},
    )

    assert resp.status_code == 200
    entry.refresh_from_db()
    assert entry.bullet == "new text"
    assert json.loads(resp["HX-Trigger"])["toast"]["variant"] == "success"


def test_invalid_post_rerenders_with_errors_without_saving(client, user):
    entry = BulletEntryFactory(user=user, bullet="keep")
    client.force_login(user)

    resp = client.post(reverse("entry-inline", kwargs={"entry_id": entry.id}), {"alias": ""})

    assert resp.status_code == 200
    assert "HX-Trigger" not in resp
    assert b"text-danger" in resp.content
    entry.refresh_from_db()
    assert entry.bullet == "keep"


def test_non_owner_gets_404(client, user, other_user):
    entry = BulletEntryFactory(user=user)
    client.force_login(other_user)
    url = reverse("entry-inline", kwargs={"entry_id": entry.id})
    assert client.get(url).status_code == 404
    assert client.post(url, {"alias": "x", "bullet": "x"}).status_code == 404


def test_editor_lazy_loads_inline_forms(client, user, cv):
    from sections.models import CVSection, SectionEntry
    from tests.factories import SectionFactory

    section = SectionFactory(user=user)
    entry = BulletEntryFactory(user=user)
    SectionEntry.objects.create(section=section, entry=entry, order=0)
    CVSection.objects.create(cv=cv, section=section, order=0)
    client.force_login(user)

    body = client.get(reverse("cv-editor", args=[cv.id])).content.decode()

    assert reverse("entry-inline", kwargs={"entry_id": entry.id}) in body
    assert 'hx-trigger="intersect once"' in body
