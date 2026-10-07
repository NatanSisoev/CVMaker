"""Side-by-side translation editing (``entry-translate``)."""

from __future__ import annotations

import json

import pytest
from django.urls import reverse

from tests.factories import ExperienceEntryFactory, PublicationEntryFactory

pytestmark = pytest.mark.django_db


def _url(entry):
    return reverse("entry-translate", kwargs={"entry_id": entry.id})


def test_get_shows_canonical_beside_existing_translation(client, user):
    entry = ExperienceEntryFactory(
        user=user, position="Engineer", translations={"es": {"position": "Ingeniera"}}
    )
    client.force_login(user)

    body = client.get(_url(entry), {"lang": "ES"}).content.decode()  # code is normalised

    assert "Engineer" in body  # canonical column
    assert 'value="Ingeniera"' in body  # translation input
    assert 'name="lang" value="es"' in body
    for field in entry.TRANSLATABLE_FIELDS:
        assert f'name="{field}"' in body


def test_post_saves_non_blank_fields_only(client, user):
    entry = PublicationEntryFactory(user=user, title="On Engines", journal="Proc.")
    client.force_login(user)

    resp = client.post(_url(entry), {"lang": "fr", "title": "Sur les moteurs", "journal": "  "})

    assert resp.status_code == 200
    entry.refresh_from_db()
    assert entry.translations == {"fr": {"title": "Sur les moteurs"}}
    assert entry.get_field("journal", language="fr") == "Proc."  # falls back
    assert json.loads(resp["HX-Trigger"])["toast"]["variant"] == "success"


def test_blanking_every_field_removes_the_language(client, user):
    entry = PublicationEntryFactory(
        user=user, translations={"fr": {"title": "x"}, "es": {"title": "y"}}
    )
    client.force_login(user)

    client.post(_url(entry), {"lang": "fr", "title": "", "journal": ""})

    entry.refresh_from_db()
    assert entry.translations == {"es": {"title": "y"}}


@pytest.mark.parametrize("code", ["", "e", "esp", "1a", "en"])
def test_bad_or_canonical_code_is_rejected_inline(client, user, code):
    entry = PublicationEntryFactory(user=user, canonical_language="en")
    client.force_login(user)

    resp = client.post(_url(entry), {"lang": code, "title": "x"})

    assert resp.status_code == 200
    assert b'role="alert"' in resp.content
    entry.refresh_from_db()
    assert entry.translations == {}


def test_non_owner_gets_404(client, user, other_user):
    entry = PublicationEntryFactory(user=user)
    client.force_login(other_user)
    assert client.get(_url(entry), {"lang": "es"}).status_code == 404
    assert client.post(_url(entry), {"lang": "es", "title": "x"}).status_code == 404


def test_detail_and_inline_pages_show_language_tabs(client, user):
    entry = PublicationEntryFactory(user=user, translations={"de": {"title": "T"}})
    client.force_login(user)

    for name in ("entry-detail", "entry-inline"):
        body = client.get(reverse(name, kwargs={"entry_id": entry.id})).content.decode()
        assert f"{_url(entry)}?lang=de" in body
        assert f'id="translate-{entry.id}"' in body
