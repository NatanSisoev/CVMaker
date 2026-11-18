"""Regressions found by clicking through the real UI."""

from __future__ import annotations

import pytest
from django.urls import reverse

from tests.factories import CVFactory

pytestmark = pytest.mark.django_db


def test_body_has_an_alpine_root_so_modal_triggers_work(client, user):
    # Buttons with x-on:click="$dispatch('open-modal', ...)" sit outside any
    # other x-data; without a root scope on <body> Alpine ignores them.
    client.force_login(user)
    html = client.get(reverse("homepage")).content.decode()
    assert "<body x-data" in html


def test_public_cv_choice_is_named_not_cv_object(client, user):
    cv = CVFactory(user=user, alias="my-public-cv")
    client.force_login(user)
    html = client.get(reverse("profile")).content.decode()
    assert "my-public-cv" in html and f"CV object ({cv.pk})" not in html


def test_settings_page_does_not_autofocus_the_password_field(client, user):
    # autofocus made the browser scroll Settings down to the password form on load.
    client.force_login(user)
    html = client.get(reverse("profile")).content.decode()
    assert "autofocus" not in html


def test_homepage_shows_the_inline_explainer_diagram(client):
    html = client.get(reverse("homepage")).content.decode()
    assert "How a CV is assembled" in html and "explainer.svg" not in html
